import os

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError

from .mpesa import initiate_stk_push
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminOrStorekeeper
from bookings.models import Booking, CreditApproval
from sales.models import Sale

from .models import Payment
from .serializers import PaymentSerializer


class BaseFinanceView:
    permission_classes = [
        IsAuthenticated,
        IsAdminOrStorekeeper,
    ]


def get_payment_totals(transaction_object, transaction_field):
    payments = Payment.objects.filter(
        **{transaction_field: transaction_object}
    )

    confirmed = payments.filter(
        status=Payment.PaymentStatus.CONFIRMED
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    pending = payments.filter(
        status=Payment.PaymentStatus.PENDING
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    return confirmed, pending


class PaymentListCreateView(
    BaseFinanceView,
    generics.ListCreateAPIView
):
    serializer_class = PaymentSerializer

    queryset = Payment.objects.select_related(
        "booking",
        "sale",
        "recorded_by",
        "verified_by",
    ).all()

    def get_queryset(self):
        queryset = super().get_queryset()

        booking_id = self.request.query_params.get("booking")
        sale_id = self.request.query_params.get("sale")
        payment_status = self.request.query_params.get("status")
        payment_method = self.request.query_params.get("payment_method")

        if booking_id:
            queryset = queryset.filter(booking_id=booking_id)

        if sale_id:
            queryset = queryset.filter(sale_id=sale_id)

        if payment_status:
            queryset = queryset.filter(status=payment_status)

        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)

        return queryset

    @transaction.atomic
    def perform_create(self, serializer):

        booking = serializer.validated_data.get("booking")
        sale = serializer.validated_data.get("sale")
        amount = serializer.validated_data["amount"]

        if booking:
            booking = Booking.objects.select_for_update().get(
                pk=booking.pk
            )

            if booking.status in [
                Booking.Status.REJECTED,
                Booking.Status.CANCELLED,
                Booking.Status.COMPLETED,
            ]:
                raise serializers.ValidationError({
                    "booking": "Payments cannot be recorded for this booking."
                })

            confirmed, pending = get_payment_totals(
                booking,
                "booking"
            )

            outstanding = (
                booking.total_amount - confirmed - pending
            )

        elif sale:
            sale = Sale.objects.select_for_update().get(
                pk=sale.pk
            )

            if sale.status in [
                Sale.Status.CANCELLED,
                Sale.Status.COMPLETED,
            ]:
                raise serializers.ValidationError({
                    "sale": "Payments cannot be recorded for this sale."
                })

            confirmed, pending = get_payment_totals(
                sale,
                "sale"
            )

            outstanding = (
                sale.total_amount - confirmed - pending
            )

        else:
            raise serializers.ValidationError({
                "transaction": "Select a booking or sale."
            })

        if amount > outstanding:
            raise serializers.ValidationError({
                "amount": (
                    f"Payment exceeds the available balance. "
                    f"Outstanding amount: {max(outstanding, Decimal('0.00'))}."
                )
            })

        serializer.save(recorded_by=self.request.user)


class PaymentVerificationView(
    BaseFinanceView,
    APIView
):

    @transaction.atomic
    def post(self, request, pk):

        initial_payment = get_object_or_404(
            Payment.objects.select_related("booking", "sale"),
            pk=pk
        )

        if initial_payment.booking_id:
            booking = Booking.objects.select_for_update().get(
                pk=initial_payment.booking_id
            )
            sale = None
            total_amount = booking.total_amount

        else:
            sale = Sale.objects.select_for_update().get(
                pk=initial_payment.sale_id
            )
            booking = None
            total_amount = sale.total_amount

        payment = Payment.objects.select_for_update().get(
            pk=pk
        )

        if payment.status != Payment.PaymentStatus.PENDING:
            return Response(
                {"error": "Only pending payments can be verified."},
                status=400
            )

        if booking:
            confirmed_total, _ = get_payment_totals(
                booking,
                "booking"
            )
            transaction_number = booking.booking_number

        else:
            confirmed_total, _ = get_payment_totals(
                sale,
                "sale"
            )
            transaction_number = sale.sale_number

        if confirmed_total + payment.amount > total_amount:
            return Response(
                {"error": "Confirming this payment would exceed the transaction total."},
                status=400
            )

        now = timezone.now()

        payment.status = Payment.PaymentStatus.CONFIRMED
        payment.verified_by = request.user
        payment.verified_at = now
        payment.paid_at = now

        payment.save(update_fields=[
            "status",
            "verified_by",
            "verified_at",
            "paid_at",
            "updated_at",
        ])

        return Response({
            "message": "Payment confirmed successfully.",
            "transaction_number": transaction_number,
            "amount": str(payment.amount),
            "payment_status": payment.status,
            "verified_by": request.user.username,
        })


class BookingPaymentBalanceView(
    BaseFinanceView,
    APIView
):

    def get(self, request, booking_id):

        booking = get_object_or_404(
            Booking,
            pk=booking_id
        )

        confirmed, pending = get_payment_totals(
            booking,
            "booking"
        )

        outstanding = max(
            booking.total_amount - confirmed,
            Decimal("0.00")
        )

        credit_approved = CreditApproval.objects.filter(
            booking=booking,
            status=CreditApproval.Status.APPROVED
        ).exists()

        fully_paid = confirmed >= booking.total_amount

        can_dispatch = (
            booking.status == Booking.Status.APPROVED
            and (fully_paid or credit_approved)
        )

        return Response({
            "transaction_type": "BOOKING",
            "booking_number": booking.booking_number,
            "booking_status": booking.status,
            "total_amount": str(booking.total_amount),
            "confirmed_payments": str(confirmed),
            "pending_payments": str(pending),
            "outstanding_balance": str(outstanding),
            "fully_paid": fully_paid,
            "credit_approved": credit_approved,
            "can_dispatch": can_dispatch,
        })


class SalePaymentBalanceView(
    BaseFinanceView,
    APIView
):

    def get(self, request, sale_id):

        sale = get_object_or_404(
            Sale,
            pk=sale_id
        )

        confirmed, pending = get_payment_totals(
            sale,
            "sale"
        )

        outstanding = max(
            sale.total_amount - confirmed,
            Decimal("0.00")
        )

        fully_paid = confirmed >= sale.total_amount

        # Sale credit approval will be implemented separately.
        credit_approved = False

        can_dispatch = (
            sale.status == Sale.Status.CONFIRMED
            and (fully_paid or credit_approved)
        )

        return Response({
            "transaction_type": "SALE",
            "sale_number": sale.sale_number,
            "sale_status": sale.status,
            "total_amount": str(sale.total_amount),
            "confirmed_payments": str(confirmed),
            "pending_payments": str(pending),
            "outstanding_balance": str(outstanding),
            "fully_paid": fully_paid,
            "credit_approved": credit_approved,
            "can_dispatch": can_dispatch,
        })

class MpesaSTKPushView(
    BaseFinanceView,
    APIView
):
    @transaction.atomic
    def post(self, request):
        booking_id = request.data.get("booking")
        sale_id = request.data.get("sale")
        phone = request.data.get("phone_number")
        amount_value = request.data.get("amount")

        if bool(booking_id) == bool(sale_id):
            raise ValidationError(
                "Provide either a booking ID or a sale ID, not both."
            )

        if not phone or not amount_value:
            raise ValidationError(
                "Phone number and amount are required."
            )

        try:
            amount = Decimal(str(amount_value))
        except Exception:
            raise ValidationError({"amount": "Enter a valid amount."})

        if not amount.is_finite() or amount <= 0:
            raise ValidationError({"amount": "Amount must be greater than zero."})

        if amount != amount.quantize(Decimal("1")):
            raise ValidationError({
                "amount": "M-Pesa STK Push amounts must be whole shillings."
            })

        if booking_id:
            booking = get_object_or_404(
                Booking.objects.select_for_update(),
                pk=booking_id
            )

            if booking.status in [
                Booking.Status.REJECTED,
                Booking.Status.CANCELLED,
                Booking.Status.COMPLETED,
            ]:
                raise ValidationError(
                    "Payments cannot be made for this booking."
                )

            confirmed, pending = get_payment_totals(
                booking, "booking"
            )

            outstanding = booking.total_amount - confirmed - pending

            if amount > outstanding:
                raise ValidationError({
                    "amount": f"Outstanding balance is {max(outstanding, Decimal('0.00'))}."
                })

            payment = Payment.objects.create(
                booking=booking,
                amount=amount,
                payment_method=Payment.PaymentMethod.MPESA,
                status=Payment.PaymentStatus.PENDING,
                recorded_by=request.user,
                mpesa_phone_number=str(phone),
                notes="M-Pesa STK Push initiated."
            )

            account_reference = booking.booking_number

        else:
            sale = get_object_or_404(
                Sale.objects.select_for_update(),
                pk=sale_id
            )

            if sale.status in [
                Sale.Status.CANCELLED,
                Sale.Status.COMPLETED,
            ]:
                raise ValidationError(
                    "Payments cannot be made for this sale."
                )

            confirmed, pending = get_payment_totals(
                sale, "sale"
            )

            outstanding = sale.total_amount - confirmed - pending

            if amount > outstanding:
                raise ValidationError({
                    "amount": f"Outstanding balance is {max(outstanding, Decimal('0.00'))}."
                })

            payment = Payment.objects.create(
                sale=sale,
                amount=amount,
                payment_method=Payment.PaymentMethod.MPESA,
                status=Payment.PaymentStatus.PENDING,
                recorded_by=request.user,
                mpesa_phone_number=str(phone),
                notes="M-Pesa STK Push initiated."
            )

            account_reference = sale.sale_number

        try:
            response_data = initiate_stk_push(
                phone_number=phone,
                amount=amount,
                account_reference=account_reference,
                transaction_desc="System payment"
            )

            checkout_id = response_data.get("CheckoutRequestID")
            merchant_id = response_data.get("MerchantRequestID")

            if response_data.get("ResponseCode") != "0" or not checkout_id:
                raise RuntimeError(
                    response_data.get(
                        "ResponseDescription",
                        "STK Push request was not accepted."
                    )
                )

            payment.mpesa_checkout_request_id = checkout_id
            payment.mpesa_merchant_request_id = merchant_id
            payment.save(update_fields=[
                "mpesa_checkout_request_id",
                "mpesa_merchant_request_id",
                "updated_at",
            ])

        except Exception as error:
            payment.status = Payment.PaymentStatus.FAILED
            payment.mpesa_result_description = str(error)
            payment.save(update_fields=[
                "status",
                "mpesa_result_description",
                "updated_at",
            ])

            raise ValidationError({
                "mpesa": "Could not initiate M-Pesa payment. Please try again."
            })

        return Response({
            "message": "STK Push sent. Ask the customer to check their phone.",
            "payment_id": payment.id,
            "checkout_request_id": checkout_id,
            "status": payment.status,
        }, status=status.HTTP_201_CREATED)


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
from bookings.models import Booking
from .models import Payment
from .serializers import PaymentSerializer


class BaseFinanceView:
    permission_classes = [
        IsAuthenticated,
        IsAdminOrStorekeeper,
    ]


class PaymentListCreateView(
    BaseFinanceView,
    generics.ListCreateAPIView
):
    serializer_class = PaymentSerializer

    queryset = Payment.objects.select_related(
        "booking",
        "recorded_by",
        "verified_by",
    ).all()

    def get_queryset(self):
        queryset = super().get_queryset()

        booking_id = self.request.query_params.get("booking")
        payment_status = self.request.query_params.get("status")
        payment_method = self.request.query_params.get("payment_method")

        if booking_id:
            queryset = queryset.filter(booking_id=booking_id)

        if payment_status:
            queryset = queryset.filter(status=payment_status)

        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)

        return queryset

    @transaction.atomic
    def perform_create(self, serializer):

        booking_id = serializer.validated_data["booking"].pk

        booking = get_object_or_404(
            Booking.objects.select_for_update(),
            pk=booking_id
        )

        amount = serializer.validated_data["amount"]

        if booking.status in [
            Booking.Status.REJECTED,
            Booking.Status.CANCELLED,
            Booking.Status.COMPLETED,
        ]:
            raise serializers.ValidationError({
                "booking": "Payments cannot be recorded for this booking."
            })

        reserved_payments = Payment.objects.filter(
            booking=booking,
            status__in=[
                Payment.PaymentStatus.PENDING,
                Payment.PaymentStatus.CONFIRMED,
            ]
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        outstanding = booking.total_amount - reserved_payments

        if amount > outstanding:
            raise serializers.ValidationError({
                "amount": (
                    f"Payment exceeds the available balance. "
                    f"Outstanding amount: {outstanding}."
                )
            })

        serializer.save(recorded_by=self.request.user)


class PaymentVerificationView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsAdminOrStorekeeper,
    ]

    @transaction.atomic
    def post(self, request, pk):

        payment = get_object_or_404(
            Payment.objects.select_related("booking"),
            pk=pk
        )

        booking = Booking.objects.select_for_update().get(
            pk=payment.booking_id
        )

        payment = Payment.objects.select_for_update().get(
            pk=pk
        )

        if payment.status != Payment.PaymentStatus.PENDING:
            return Response(
                {"error": "Only pending payments can be verified."},
                status=400
            )

        confirmed_total = Payment.objects.filter(
            booking=booking,
            status=Payment.PaymentStatus.CONFIRMED,
        ).exclude(pk=payment.pk).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        if confirmed_total + payment.amount > booking.total_amount:
            return Response(
                {"error": "Confirming this payment would exceed the booking total."},
                status=400
            )

        payment.status = Payment.PaymentStatus.CONFIRMED
        payment.verified_by = request.user
        payment.verified_at = timezone.now()
        payment.paid_at = timezone.now()

        payment.save(update_fields=[
            "status",
            "verified_by",
            "verified_at",
            "paid_at",
            "updated_at",
        ])

        return Response({
            "message": "Payment confirmed successfully.",
            "payment_id": payment.id,
            "booking_number": booking.booking_number,
            "amount": str(payment.amount),
            "payment_status": payment.status,
            "verified_by": request.user.username,
        })

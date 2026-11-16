
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404

from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminOrStorekeeper, IsAdminRole
from inventory.models import Material, StockMovement

from .models import Sale, SaleItem, SaleCreditApproval
from .serializers import SaleSerializer
from finance.models import Payment

class BaseSalesView:
    permission_classes = [
        IsAuthenticated,
        IsAdminOrStorekeeper,
    ]


class SaleListCreateView(
    BaseSalesView,
    generics.ListCreateAPIView
):
    serializer_class = SaleSerializer

    def get_queryset(self):
        queryset = Sale.objects.select_related(
            "created_by"
        ).prefetch_related(
            "items",
            "items__material"
        ).order_by("-created_at")

        status = self.request.query_params.get("status")
        phone = self.request.query_params.get("customer_phone")
        sale_number = self.request.query_params.get("sale_number")

        if status:
            queryset = queryset.filter(status=status)

        if phone:
            queryset = queryset.filter(
                customer_phone__icontains=phone
            )

        if sale_number:
            queryset = queryset.filter(
                sale_number__icontains=sale_number
            )

        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class SaleDetailView(
    BaseSalesView,
    generics.RetrieveAPIView
):
    serializer_class = SaleSerializer

    queryset = Sale.objects.select_related(
        "created_by"
    ).prefetch_related(
        "items",
        "items__material"
    )


class SaleConfirmationView(
    BaseSalesView,
    APIView
):

    @transaction.atomic
    def post(self, request, pk):

        sale = get_object_or_404(
            Sale.objects.select_for_update(),
            pk=pk
        )

        if sale.status != Sale.Status.PENDING:
            return Response(
                {"detail": "Only pending sales can be confirmed."},
                status=400
            )

        if sale.payment_arrangement == Sale.PaymentArrangement.CREDIT:

            approval = SaleCreditApproval.objects.filter(
                sale=sale
            ).first()

            if not approval or approval.status != SaleCreditApproval.Status.APPROVED:
                return Response(
                    {"detail": "This credit sale has not been approved by Admin."},
                    status=400
                )

        sale_items = list(
            SaleItem.objects.filter(
                sale=sale
            ).select_related("material")
        )

        material_ids = sorted({
            item.material_id for item in sale_items
        })

        materials = {
            material.pk: material
            for material in Material.objects.select_for_update().filter(
                pk__in=material_ids
            ).order_by("pk")
        }

        for item in sale_items:
            material = materials[item.material_id]

            if not material.is_active:
                raise serializers.ValidationError({
                    "material": f"{material.name} is inactive."
                })

            if material.stock_quantity < item.quantity:
                raise serializers.ValidationError({
                    "stock": (
                        f"Insufficient stock for {material.name}. "
                        f"Available: {material.stock_quantity}, "
                        f"Requested: {item.quantity}."
                    )
                })

        for item in sale_items:
            material = materials[item.material_id]

            material.stock_quantity -= item.quantity

            material.save(update_fields=[
                "stock_quantity",
                "updated_at"
            ])

            StockMovement.objects.create(
                material=material,
                movement_type=StockMovement.MovementType.STOCK_OUT,
                quantity=item.quantity,
                reference=sale.sale_number,
                notes="Material issued for confirmed sale.",
                recorded_by=request.user
            )

        sale.status = Sale.Status.CONFIRMED
        sale.save(update_fields=[
            "status",
            "updated_at"
        ])

        return Response({
            "detail": "Sale confirmed and stock deducted.",
            "sale": SaleSerializer(sale).data
        })


class SaleCancellationView(
    BaseSalesView,
    APIView
):

    @transaction.atomic
    def post(self, request, pk):

        sale = get_object_or_404(
            Sale.objects.select_for_update(),
            pk=pk
        )

        if sale.status not in [
            Sale.Status.PENDING,
            Sale.Status.CONFIRMED,
        ]:
            return Response(
                {"detail": "This sale cannot be cancelled."},
                status=400
            )

        # Stock restoration for confirmed sales will be
        # handled through a controlled stock movement.
        if sale.status == Sale.Status.CONFIRMED:

            sale_items = list(
                SaleItem.objects.filter(
                    sale=sale
                ).select_related("material")
            )

            material_ids = sorted({
                item.material_id for item in sale_items
            })

            materials = {
                material.pk: material
                for material in Material.objects.select_for_update().filter(
                    pk__in=material_ids
                ).order_by("pk")
            }

            for item in sale_items:
                material = materials[item.material_id]

                material.stock_quantity += item.quantity

                material.save(update_fields=[
                    "stock_quantity",
                    "updated_at"
                ])

                StockMovement.objects.create(
                    material=material,
                    movement_type=StockMovement.MovementType.STOCK_IN,
                    quantity=item.quantity,
                    reference=sale.sale_number,
                    notes="Stock restored after sale cancellation.",
                    recorded_by=request.user
                )

        sale.status = Sale.Status.CANCELLED
        sale.save(update_fields=[
            "status",
            "updated_at"
        ])

        return Response({
            "detail": "Sale cancelled successfully."
        })


class SaleDispatchView(
    BaseSalesView,
    APIView
):

    @transaction.atomic
    def post(self, request, pk):

        sale = get_object_or_404(
            Sale.objects.select_for_update(),
            pk=pk
        )

        if sale.status != Sale.Status.CONFIRMED:
            return Response(
                {"detail": "Only confirmed sales can be dispatched."},
                status=400
            )

        # Credit sales require Admin approval.
        if sale.payment_arrangement == Sale.PaymentArrangement.CREDIT:

            approval = SaleCreditApproval.objects.filter(
                sale=sale
            ).first()

            if not approval or approval.status != SaleCreditApproval.Status.APPROVED:
                return Response(
                    {"detail": "Credit sale has not been approved by Admin."},
                    status=400
                )

        # Full-payment sales must be fully paid.
        else:

            confirmed_payments = Payment.objects.filter(
                sale=sale,
                status=Payment.Status.CONFIRMED
            ).aggregate(
                total=Sum("amount")
            )["total"] or Decimal("0.00")

            outstanding = sale.total_amount - confirmed_payments

            if outstanding > 0:
                return Response({
                    "detail": "Full payment is required before dispatch.",
                    "total_amount": str(sale.total_amount),
                    "amount_paid": str(confirmed_payments),
                    "outstanding_balance": str(outstanding),
                }, status=400)

        sale.status = Sale.Status.DISPATCHED

        sale.save(update_fields=[
            "status",
            "updated_at"
        ])

        return Response({
            "detail": "Sale marked as dispatched.",
            "sale_number": sale.sale_number,
            "status": sale.status,
        })




class SaleCompletionView(
    BaseSalesView,
    APIView
):

    def post(self, request, pk):

        sale = get_object_or_404(Sale, pk=pk)

        if sale.status not in [
            Sale.Status.READY,
            Sale.Status.DISPATCHED,
        ]:
            return Response(
                {"detail": "Sale is not ready for completion."},
                status=400
            )

        sale.status = Sale.Status.COMPLETED
        sale.save(update_fields=[
            "status",
            "updated_at"
        ])

        return Response({
            "detail": "Sale completed successfully."
        })

class SaleCreditApprovalListView(
    BaseSalesView,
    generics.ListAPIView
):
    permission_classes = [
        IsAuthenticated,
        IsAdminRole,
    ]

    def get_queryset(self):
        queryset = SaleCreditApproval.objects.select_related(
            "sale",
            "reviewed_by"
        ).order_by("-requested_at")

        approval_status = self.request.query_params.get("status")

        if approval_status:
            queryset = queryset.filter(status=approval_status)

        return queryset

    def list(self, request, *args, **kwargs):
        approvals = self.get_queryset()

        data = []

        for approval in approvals:
            data.append({
                "id": approval.id,
                "sale_id": approval.sale_id,
                "sale_number": approval.sale.sale_number,
                "customer_name": approval.sale.customer_name,
                "customer_phone": approval.sale.customer_phone,
                "total_amount": approval.sale.total_amount,
                "status": approval.status,
                "reviewed_by": (
                    approval.reviewed_by.username
                    if approval.reviewed_by else None
                ),
                "reviewed_at": approval.reviewed_at,
                "reason": approval.reason,
                "review_notes": approval.review_notes,
                "requested_at": approval.requested_at,
            })

        return Response(data)


class SaleCreditApprovalDecisionView(
    BaseSalesView,
    APIView
):
    permission_classes = [
        IsAuthenticated,
        IsAdminRole,
    ]

    @transaction.atomic
    def post(self, request, pk):

        approval = get_object_or_404(
            SaleCreditApproval.objects.select_for_update().select_related("sale"),
            pk=pk
        )

        if approval.status != SaleCreditApproval.Status.PENDING:
            return Response(
                {"detail": "This credit request has already been reviewed."},
                status=400
            )

        decision = request.data.get("status")

        if decision not in [
            SaleCreditApproval.Status.APPROVED,
            SaleCreditApproval.Status.REJECTED,
        ]:
            return Response(
                {"detail": "Choose APPROVED or REJECTED."},
                status=400
            )

        if approval.sale.status != Sale.Status.PENDING:
            return Response(
                {"detail": "Only pending sales can receive credit approval."},
                status=400
            )

        approval.status = decision
        approval.reviewed_by = request.user
        approval.reviewed_at = timezone.now()
        approval.review_notes = request.data.get("review_notes", "")

        approval.save(update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_notes",
        ])

        return Response({
            "detail": f"Credit request {decision.lower()} successfully.",
            "sale_number": approval.sale.sale_number,
            "approval_status": approval.status,
            "reviewed_by": request.user.username,
            "reviewed_at": approval.reviewed_at,
        })


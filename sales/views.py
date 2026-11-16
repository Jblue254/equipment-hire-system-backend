
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404

from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminOrStorekeeper
from inventory.models import Material, StockMovement

from .models import Sale, SaleItem
from .serializers import SaleSerializer


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
            return Response(
                {"detail": "Credit sales require Admin approval."},
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

    def post(self, request, pk):

        sale = get_object_or_404(Sale, pk=pk)

        if sale.status != Sale.Status.CONFIRMED:
            return Response(
                {"detail": "Only confirmed sales can be dispatched."},
                status=400
            )

        sale.status = Sale.Status.DISPATCHED
        sale.save(update_fields=[
            "status",
            "updated_at"
        ])

        return Response({
            "detail": "Sale marked as dispatched."
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

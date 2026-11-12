
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import generics, filters, status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsAdminOrStorekeeper

from .models import (
    EquipmentCategory,
    Equipment,
    MaterialCategory,
    Material,
    StockMovement,
    EquipmentUnit,
    MaintenanceRecord,
)

from .serializers import (
    EquipmentCategorySerializer,
    EquipmentSerializer,
    MaterialCategorySerializer,
    MaterialSerializer,
    StockMovementSerializer,
    EquipmentUnitSerializer,
)

from .maintenance_serializers import MaintenanceRecordSerializer



class BaseInventoryView:
    permission_classes = [
        IsAuthenticated,
        IsAdminOrStorekeeper,
    ]


def sync_individual_equipment(equipment):
    """
    Recalculate parent equipment quantities and summary status
    from its registered physical units.
    """

    units = EquipmentUnit.objects.filter(
        equipment=equipment
    )

    total = units.count()

    available = units.filter(
        status=EquipmentUnit.Status.AVAILABLE
    ).count()

    equipment.total_quantity = total
    equipment.available_quantity = available

    if total > 0:

        if available > 0:
            equipment.status = Equipment.Status.AVAILABLE

        elif units.filter(
            status=EquipmentUnit.Status.HIRED_OUT
        ).exists():
            equipment.status = Equipment.Status.HIRED_OUT

        elif units.filter(
            status=EquipmentUnit.Status.RESERVED
        ).exists():
            equipment.status = Equipment.Status.RESERVED

        elif units.filter(
            status=EquipmentUnit.Status.UNDER_MAINTENANCE
        ).exists():
            equipment.status = Equipment.Status.UNDER_MAINTENANCE

        elif units.filter(
            status=EquipmentUnit.Status.DAMAGED
        ).exists():
            equipment.status = Equipment.Status.DAMAGED

        else:
            equipment.status = Equipment.Status.RETIRED

    equipment.save(update_fields=[
        "total_quantity",
        "available_quantity",
        "status",
        "updated_at",
    ])



# EQUIPMENT CATEGORIES

class EquipmentCategoryListCreateView(
    BaseInventoryView,
    generics.ListCreateAPIView
):
    queryset = EquipmentCategory.objects.all()
    serializer_class = EquipmentCategorySerializer


class EquipmentCategoryDetailView(
    BaseInventoryView,
    generics.RetrieveUpdateAPIView
):
    queryset = EquipmentCategory.objects.all()
    serializer_class = EquipmentCategorySerializer


# EQUIPMENT

class EquipmentListCreateView(
    BaseInventoryView,
    generics.ListCreateAPIView
):
    queryset = Equipment.objects.select_related("category").all()
    serializer_class = EquipmentSerializer

    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    search_fields = [
        "name",
        "identification_number",
        "category__name",
    ]

    ordering_fields = [
        "name",
        "created_at",
        "daily_rate",
    ]


class EquipmentDetailView(
    BaseInventoryView,
    generics.RetrieveUpdateAPIView
):
    queryset = Equipment.objects.select_related("category").all()
    serializer_class = EquipmentSerializer


# EQUIPMENT UNITS

class EquipmentUnitListCreateView(
    BaseInventoryView,
    generics.ListCreateAPIView
):
    queryset = EquipmentUnit.objects.select_related(
        "equipment",
        "equipment__category"
    ).all()

    serializer_class = EquipmentUnitSerializer

    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    search_fields = [
        "asset_number",
        "equipment__name",
    ]

    ordering_fields = [
        "asset_number",
        "created_at",
        "status",
    ]

    def get_queryset(self):
        queryset = super().get_queryset()

        status_filter = self.request.query_params.get("status")
        equipment_id = self.request.query_params.get("equipment")

        if status_filter:
            queryset = queryset.filter(status=status_filter)

        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)

        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        equipment_id = serializer.validated_data["equipment"].id

        equipment = Equipment.objects.select_for_update().get(
            pk=equipment_id
        )

        if equipment.tracking_type != "INDIVIDUAL":
            raise serializers.ValidationError({
                "equipment": "Only individually tracked equipment can have units."
            })

        serializer.save(equipment=equipment)

        # Recalculate quantities from the actual units.
        sync_individual_equipment(equipment)


class EquipmentUnitDetailView(
    BaseInventoryView,
    generics.RetrieveAPIView
):
    queryset = EquipmentUnit.objects.select_related(
        "equipment"
    ).all()

    serializer_class = EquipmentUnitSerializer


# MATERIAL CATEGORIES

class MaterialCategoryListCreateView(
    BaseInventoryView,
    generics.ListCreateAPIView
):
    queryset = MaterialCategory.objects.all()
    serializer_class = MaterialCategorySerializer


class MaterialCategoryDetailView(
    BaseInventoryView,
    generics.RetrieveUpdateAPIView
):
    queryset = MaterialCategory.objects.all()
    serializer_class = MaterialCategorySerializer


# MATERIALS

class MaterialListCreateView(
    BaseInventoryView,
    generics.ListCreateAPIView
):
    queryset = Material.objects.select_related("category").all()
    serializer_class = MaterialSerializer

    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    search_fields = [
        "name",
        "category__name",
    ]

    ordering_fields = [
        "name",
        "stock_quantity",
        "selling_price",
    ]


class MaterialDetailView(
    BaseInventoryView,
    generics.RetrieveUpdateAPIView
):
    queryset = Material.objects.select_related("category").all()
    serializer_class = MaterialSerializer


# STOCK MOVEMENTS

class StockMovementListCreateView(
    BaseInventoryView,
    generics.ListCreateAPIView
):
    serializer_class = StockMovementSerializer

    def get_queryset(self):
        return StockMovement.objects.select_related(
            "material",
            "recorded_by"
        ).all()

    @transaction.atomic
    def perform_create(self, serializer):
        material_id = serializer.validated_data["material"].id
        movement_type = serializer.validated_data["movement_type"]
        quantity = serializer.validated_data["quantity"]

        material = Material.objects.select_for_update().get(
            pk=material_id
        )

        quantity = Decimal(str(quantity))

        if quantity <= 0:
            raise serializers.ValidationError({
                "quantity": "Quantity must be greater than zero."
            })

        if movement_type == StockMovement.MovementType.STOCK_IN:
            material.stock_quantity += quantity

        elif movement_type == StockMovement.MovementType.STOCK_OUT:
            if material.stock_quantity < quantity:
                raise serializers.ValidationError({
                    "quantity": "Insufficient stock."
                })

            material.stock_quantity -= quantity

        elif movement_type == StockMovement.MovementType.ADJUSTMENT:
            # For an adjustment, quantity represents the new stock balance.
            material.stock_quantity = quantity

        else:
            raise serializers.ValidationError({
                "movement_type": "Invalid movement type."
            })

        material.save(update_fields=[
            "stock_quantity",
            "updated_at",
        ])

        serializer.save(recorded_by=self.request.user)


# MAINTENANCE

class MaintenanceListCreateView(
    BaseInventoryView,
    generics.ListCreateAPIView
):
    serializer_class = MaintenanceRecordSerializer

    queryset = MaintenanceRecord.objects.select_related(
        "equipment",
        "unit",
        "recorded_by"
    ).all()

    @transaction.atomic
    def perform_create(self, serializer):
        equipment_id = serializer.validated_data["equipment"].id

        equipment = Equipment.objects.select_for_update().get(
            pk=equipment_id
        )

        quantity = serializer.validated_data.get(
            "quantity_affected",
            1
        )

        unit = serializer.validated_data.get("unit")

        if equipment.tracking_type == "INDIVIDUAL":

            if not unit:
                raise serializers.ValidationError({
                    "unit": "Select the specific equipment unit."
                })

            unit = EquipmentUnit.objects.select_for_update().get(
                pk=unit.pk
            )

            if unit.status != EquipmentUnit.Status.AVAILABLE:
                raise serializers.ValidationError({
                    "unit": "This unit is not available for maintenance allocation."
                })

            unit.status = EquipmentUnit.Status.UNDER_MAINTENANCE
            unit.save(update_fields=["status", "updated_at"])

            equipment.available_quantity = max(
                0,
                equipment.available_quantity - 1
            )

        else:
            if quantity > equipment.available_quantity:
                raise serializers.ValidationError({
                    "quantity_affected": "There is not enough available equipment for this maintenance record."
                })

            equipment.available_quantity -= quantity

        equipment.save(update_fields=[
            "available_quantity",
            "updated_at",
        ])

        serializer.save(
            equipment=equipment,
            recorded_by=self.request.user,
            condition_cleared=False,
        )


class MaintenanceDetailView(
    BaseInventoryView,
    generics.RetrieveUpdateAPIView
):
    queryset = MaintenanceRecord.objects.select_related(
        "equipment",
        "unit",
        "recorded_by"
    ).all()

    serializer_class = MaintenanceRecordSerializer

    @transaction.atomic
    def perform_update(self, serializer):
        record = MaintenanceRecord.objects.select_for_update().get(
            pk=self.get_object().pk
        )

        equipment = Equipment.objects.select_for_update().get(
            pk=record.equipment_id
        )

        # Equipment, unit and affected quantity cannot be changed
        # after a maintenance record has been created.
        for field in ("equipment", "unit", "quantity_affected"):
            if field in serializer.validated_data:
                raise serializers.ValidationError({
                    field: "This field cannot be changed after maintenance is recorded."
                })

        old_condition_cleared = record.condition_cleared

        updated_record = serializer.save(
            equipment=equipment,
            unit=record.unit,
            quantity_affected=record.quantity_affected,
            recorded_by=record.recorded_by,
        )

        # Release equipment only when maintenance is completed or
        # cancelled AND its condition has been explicitly cleared.
        can_release = (
            updated_record.status in (
                MaintenanceRecord.Status.COMPLETED,
                MaintenanceRecord.Status.CANCELLED,
            )
            and updated_record.condition_cleared
            and not old_condition_cleared
        )

        if can_release:

            if equipment.tracking_type == "INDIVIDUAL":
                unit = EquipmentUnit.objects.select_for_update().get(
                    pk=record.unit_id
                )

                unit.status = EquipmentUnit.Status.AVAILABLE
                unit.save(update_fields=["status", "updated_at"])

                equipment.available_quantity = (
                    EquipmentUnit.objects.filter(
                        equipment=equipment,
                        status=EquipmentUnit.Status.AVAILABLE
                    ).count()
                )

            else:
                equipment.available_quantity += record.quantity_affected

                if equipment.available_quantity > equipment.total_quantity:
                    raise serializers.ValidationError({
                        "condition_cleared": "Cannot release more equipment than the total quantity."
                    })

            equipment.save(update_fields=[
                "available_quantity",
                "updated_at",
            ])

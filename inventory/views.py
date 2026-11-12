from django.db import transaction
from rest_framework import generics, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers
from .models import MaintenanceRecord
from .maintenance_serializers import MaintenanceRecordSerializer


from accounts.permissions import IsAdminOrStorekeeper

from .models import (
    EquipmentCategory,
    Equipment,
    MaterialCategory,
    Material,
    StockMovement,
    EquipmentUnit,
)

from .serializers import (
    EquipmentCategorySerializer,
    EquipmentSerializer,
    MaterialCategorySerializer,
    MaterialSerializer,
    StockMovementSerializer,
    EquipmentUnitSerializer,
)


class BaseInventoryView:
    permission_classes = [
        IsAuthenticated,
        IsAdminOrStorekeeper,
    ]


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
        material_id = self.request.data.get("material")
        movement_type = self.request.data.get("movement_type")
        quantity = self.request.data.get("quantity")

        material = Material.objects.select_for_update().get(
            pk=material_id
        )

        quantity = float(quantity)

        if quantity <= 0:
            raise serializers.ValidationError(
                {"quantity": "Quantity must be greater than zero."}
            )

        if movement_type == StockMovement.MovementType.STOCK_IN:
            material.stock_quantity += quantity

        elif movement_type == StockMovement.MovementType.STOCK_OUT:
            if material.stock_quantity < quantity:
                raise serializers.ValidationError(
                    {"quantity": "Insufficient stock."}
                )

            material.stock_quantity -= quantity

        elif movement_type == StockMovement.MovementType.ADJUSTMENT:
            material.stock_quantity = quantity

        else:
            raise serializers.ValidationError(
                {"movement_type": "Invalid movement type."}
            )

        material.save(update_fields=["stock_quantity", "updated_at"])

        serializer.save(recorded_by=self.request.user)

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

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)


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

from rest_framework import serializers

from .models import (
    EquipmentCategory,
    Equipment,
    MaterialCategory,
    Material,
    StockMovement,
    EquipmentUnit,
)


class EquipmentCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentCategory
        fields = "__all__"


class EquipmentSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(
        source="category.name",
        read_only=True
    )

    class Meta:
        model = Equipment
        fields = "__all__"

        read_only_fields = (
            "id",
            "available_quantity",
            "status",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        tracking_type = attrs.get(
            "tracking_type",
            getattr(self.instance, "tracking_type", None)
        )

        total_quantity = attrs.get(
            "total_quantity",
            getattr(self.instance, "total_quantity", 1)
        )

        if total_quantity < 1:
            raise serializers.ValidationError({
                "total_quantity": "Total quantity must be at least 1."
            })

        if tracking_type == "INDIVIDUAL" and self.instance:
            if tracking_type != self.instance.tracking_type:
                raise serializers.ValidationError({
                    "tracking_type": "You cannot change the tracking type after equipment has been created."
                })

        return attrs


class MaterialCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialCategory
        fields = "__all__"


class MaterialSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(
        source="category.name",
        read_only=True
    )

    class Meta:
        model = Material
        fields = "__all__"

        read_only_fields = (
            "id",
            "stock_quantity",
            "created_at",
            "updated_at",
        )


class StockMovementSerializer(serializers.ModelSerializer):
    recorded_by = serializers.StringRelatedField(
        read_only=True
    )

    class Meta:
        model = StockMovement
        fields = "__all__"

        read_only_fields = (
            "id",
            "recorded_by",
            "created_at",
        )

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Movement quantity must be greater than zero."
            )

        return value


class EquipmentUnitSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(
        source="equipment.name",
        read_only=True
    )

    class Meta:
        model = EquipmentUnit
        fields = "__all__"

        read_only_fields = (
            "id",
            "status",
            "created_at",
            "updated_at",
        )

    def validate_equipment(self, equipment):
        if equipment.tracking_type != "INDIVIDUAL":
            raise serializers.ValidationError(
                "Equipment units can only be created "
                "for individually tracked equipment."
            )

        return equipment


from rest_framework import serializers

from .models import (
    EquipmentCategory,
    Equipment,
    MaterialCategory,
    Material,
    StockMovement,
    EquipmentUnit,
    MaintenanceRecord,
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

        # Do not allow changing tracking methods after creation.
        if self.instance:
            if tracking_type != self.instance.tracking_type:
                raise serializers.ValidationError({
                    "tracking_type": (
                        "You cannot change the tracking type "
                        "after equipment has been created."
                    )
                })

            # Quantity changes need a dedicated stock adjustment
            # process so existing bookings and maintenance are protected.
            if "total_quantity" in attrs:
                raise serializers.ValidationError({
                    "total_quantity": (
                        "Use an equipment stock adjustment process "
                        "to change the total quantity."
                    )
                })

        # Individual equipment quantity is calculated from registered units.
        if tracking_type == "INDIVIDUAL":
            attrs["total_quantity"] = 0

        elif total_quantity < 1:
            raise serializers.ValidationError({
                "total_quantity": "Total quantity must be at least 1."
            })

        return attrs

    def create(self, validated_data):
        tracking_type = validated_data.get("tracking_type")

        if tracking_type == "INDIVIDUAL":
            validated_data["total_quantity"] = 0
            validated_data["available_quantity"] = 0

        else:
            quantity = validated_data.get("total_quantity", 1)
            validated_data["available_quantity"] = quantity

        return super().create(validated_data)



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





class MaintenanceRecordSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(
        source="equipment.name",
        read_only=True
    )

    unit_asset_number = serializers.CharField(
        source="unit.asset_number",
        read_only=True
    )

    recorded_by = serializers.StringRelatedField(
        read_only=True
    )

    class Meta:
        model = MaintenanceRecord
        fields = "__all__"

        read_only_fields = (
            "id",
            "date_reported",
            "recorded_by",
            "created_at",
        )

    def validate(self, attrs):
        equipment = attrs.get(
            "equipment",
            getattr(self.instance, "equipment", None)
        )

        unit = attrs.get(
            "unit",
            getattr(self.instance, "unit", None)
        )

        quantity = attrs.get(
            "quantity_affected",
            getattr(self.instance, "quantity_affected", 1)
        )

        if equipment:
            if unit and unit.equipment_id != equipment.id:
                raise serializers.ValidationError({
                    "unit": "Selected unit does not belong to this equipment."
                })

            if unit and quantity != 1:
                raise serializers.ValidationError({
                    "quantity_affected": "Individual units must have quantity 1."
                })

            if not unit and equipment.tracking_type == "INDIVIDUAL":
                raise serializers.ValidationError({
                    "unit": "Select a physical unit for individually tracked equipment."
                })

            if (
                not unit
                and equipment.tracking_type == "QUANTITY"
                and quantity > equipment.total_quantity
            ):
                raise serializers.ValidationError({
                    "quantity_affected": "Maintenance quantity exceeds total equipment stock."
                })

        if quantity < 1:
            raise serializers.ValidationError({
                "quantity_affected": "Quantity affected must be at least 1."
            })

        return attrs


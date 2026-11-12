
from rest_framework import serializers
from .models import MaintenanceRecord


class MaintenanceRecordSerializer(serializers.ModelSerializer):

    equipment_name = serializers.CharField(
        source="equipment.name",
        read_only=True
    )

    asset_number = serializers.CharField(
        source="unit.asset_number",
        read_only=True,
        allow_null=True
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

        if not equipment:
            raise serializers.ValidationError({
                "equipment": "Equipment is required."
            })

        if quantity < 1:
            raise serializers.ValidationError({
                "quantity_affected": "Quantity must be at least 1."
            })

        # Individual equipment must have a specific unit selected.
        if equipment.tracking_type == "INDIVIDUAL":

            if not unit:
                raise serializers.ValidationError({
                    "unit": "Select the specific equipment unit."
                })

            if unit.equipment_id != equipment.id:
                raise serializers.ValidationError({
                    "unit": "This unit does not belong to the selected equipment."
                })

            if quantity != 1:
                raise serializers.ValidationError({
                    "quantity_affected": "Individual equipment maintenance must affect one unit."
                })

        # Quantity-based equipment does not use individual units.
        elif equipment.tracking_type == "QUANTITY":

            if unit:
                raise serializers.ValidationError({
                    "unit": "Do not select an individual unit for quantity-based equipment."
                })

            if quantity > equipment.total_quantity:
                raise serializers.ValidationError({
                    "quantity_affected": "Maintenance quantity cannot exceed total equipment quantity."
                })
            status_value = attrs.get(
            "status",
            getattr(self.instance, "status", None)
        )

        condition_cleared = attrs.get(
            "condition_cleared",
            getattr(self.instance, "condition_cleared", False)
        )

        if condition_cleared and status_value not in (
            MaintenanceRecord.Status.COMPLETED,
            MaintenanceRecord.Status.CANCELLED,
        ):
            raise serializers.ValidationError({
                "condition_cleared": (
                    "Maintenance must be completed or cancelled "
                    "before equipment can be cleared."
                )
            })
            

        return attrs

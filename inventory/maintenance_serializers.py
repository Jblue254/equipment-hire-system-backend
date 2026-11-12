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

        if unit and equipment and unit.equipment_id != equipment.id:
            raise serializers.ValidationError({
                "unit": "This unit does not belong to the selected equipment."
            })

        return attrs
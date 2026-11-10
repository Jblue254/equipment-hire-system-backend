from rest_framework import serializers
from .models import (
    EquipmentCategory,
    Equipment,
    MaterialCategory,
    Material,
    StockMovement,
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


class StockMovementSerializer(serializers.ModelSerializer):
    recorded_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = StockMovement
        fields = "__all__"

        read_only_fields = (
            "id",
            "recorded_by",
            "created_at",
        )
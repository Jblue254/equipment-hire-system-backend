from django.contrib import admin
from .models import (
    EquipmentCategory,
    Equipment,
    MaterialCategory,
    Material,
    StockMovement,
)


@admin.register(EquipmentCategory)
class EquipmentCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "tracking_type",
        "total_quantity",
        "available_quantity",
        "status",
        "is_active",
    )

    list_filter = ("category", "tracking_type", "status", "is_active")
    search_fields = ("name", "identification_number")


@admin.register(MaterialCategory)
class MaterialCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "unit",
        "stock_quantity",
        "selling_price",
        "is_active",
    )

    list_filter = ("category", "unit", "is_active")
    search_fields = ("name",)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "material",
        "movement_type",
        "quantity",
        "recorded_by",
        "created_at",
    )

    list_filter = ("movement_type", "created_at")
    search_fields = ("material__name", "reference")
    readonly_fields = ("created_at",)
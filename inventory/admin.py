from django.contrib import admin
from .models import (
    EquipmentCategory,
    Equipment,
    MaterialCategory,
    Material,
    StockMovement,
    EquipmentUnit,
    MaintenanceRecord,
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

@admin.register(EquipmentUnit)
class EquipmentUnitAdmin(admin.ModelAdmin):

    list_display = (
        "asset_number",
        "equipment",
        "status",
        "date_acquired",
    )

    list_filter = ("status", "equipment__category")

    search_fields = (
        "asset_number",
        "equipment__name",
    )
    
@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):

    list_display = (
        "equipment",
        "unit",
        "maintenance_type",
        "status",
        "repair_cost",
        "date_reported",
        "date_completed",
    )

    list_filter = (
        "maintenance_type",
        "status",
        "date_reported",
    )

    search_fields = (
        "equipment__name",
        "unit__asset_number",
        "problem_reported",
        "service_provider",
    )

    readonly_fields = (
        "date_reported",
        "created_at",
    )
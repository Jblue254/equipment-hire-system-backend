
from django.contrib import admin
from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "sale_number",
        "customer_name",
        "customer_phone",
        "total_amount",
        "status",
        "payment_arrangement",
        "created_at",
    )

    list_filter = (
        "status",
        "payment_arrangement",
        "transport_required",
        "created_at",
    )

    search_fields = (
        "sale_number",
        "customer_name",
        "customer_phone",
    )

    readonly_fields = (
        "sale_number",
        "subtotal",
        "total_amount",
        "created_at",
        "updated_at",
    )

    inlines = [SaleItemInline]


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = (
        "sale",
        "material",
        "quantity",
        "unit_price",
        "line_total",
    )

    search_fields = (
        "sale__sale_number",
        "material__name",
    )

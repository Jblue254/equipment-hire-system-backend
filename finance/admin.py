from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "booking",
        "amount",
        "payment_method",
        "status",
        "transaction_reference",
        "created_at",
    )

    list_filter = (
        "payment_method",
        "status",
        "created_at",
    )

    search_fields = (
        "booking__booking_number",
        "transaction_reference",
        "receipt_number",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )
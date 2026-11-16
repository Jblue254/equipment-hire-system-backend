
from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):

    booking_number = serializers.CharField(
        source="booking.booking_number",
        read_only=True,
        allow_null=True
    )

    sale_number = serializers.CharField(
        source="sale.sale_number",
        read_only=True,
        allow_null=True
    )

    recorded_by_name = serializers.CharField(
        source="recorded_by.username",
        read_only=True
    )

    verified_by_name = serializers.CharField(
        source="verified_by.username",
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = Payment

        fields = [
            "id",
            "booking",
            "booking_number",
            "sale",
            "sale_number",
            "amount",
            "payment_method",
            "status",
            "transaction_reference",
            "receipt_number",
            "recorded_by",
            "recorded_by_name",
            "verified_by",
            "verified_by_name",
            "paid_at",
            "verified_at",
            "notes",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "status",
            "transaction_reference",
            "receipt_number",
            "recorded_by",
            "verified_by",
            "paid_at",
            "verified_at",
            "created_at",
            "updated_at",
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Payment amount must be greater than zero."
            )

        return value

    def validate(self, attrs):

        booking = attrs.get(
            "booking",
            getattr(self.instance, "booking", None)
        )

        sale = attrs.get(
            "sale",
            getattr(self.instance, "sale", None)
        )

        # Exactly one transaction must be selected.
        if bool(booking) == bool(sale):
            raise serializers.ValidationError({
                "transaction": (
                    "Select exactly one booking or sale."
                )
            })

        if booking:
            if booking.status in [
                "REJECTED",
                "CANCELLED",
                "COMPLETED",
            ]:
                raise serializers.ValidationError({
                    "booking": (
                        "Payments cannot be recorded for this booking."
                    )
                })

        if sale:
            if sale.status in [
                "CANCELLED",
                "COMPLETED",
            ]:
                raise serializers.ValidationError({
                    "sale": (
                        "Payments cannot be recorded for this sale."
                    )
                })

        return attrs

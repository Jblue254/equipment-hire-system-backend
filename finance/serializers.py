
from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    booking_number = serializers.CharField(
        source="booking.booking_number",
        read_only=True
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
        booking = attrs.get("booking")

        if booking:
            if booking.status in [
                "REJECTED",
                "CANCELLED",
                "COMPLETED",
            ]:
                raise serializers.ValidationError({
                    "booking": "Payments cannot be recorded for this booking."
                })

        return attrs

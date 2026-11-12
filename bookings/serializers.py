
from decimal import Decimal
from uuid import uuid4

from django.utils import timezone

from rest_framework import serializers

from .models import (
    Booking,
    BookingItem,
    CreditApproval,
    BookingReturn,
    ReturnItem,
)


class BookingItemSerializer(serializers.ModelSerializer):

    equipment_name = serializers.CharField(
        source="equipment.name",
        read_only=True
    )

    asset_number = serializers.CharField(
        source="equipment_unit.asset_number",
        read_only=True,
        allow_null=True
    )

    line_total = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = BookingItem

        fields = (
            "id",
            "equipment",
            "equipment_name",
            "equipment_unit",
            "asset_number",
            "quantity",
            "rate_period",
            "hire_rate",
            "duration_units",
            "line_total",
        )

        read_only_fields = ("id", "line_total")

    def validate(self, attrs):
        equipment = attrs.get("equipment")
        unit = attrs.get("equipment_unit")
        quantity = attrs.get("quantity", 1)

        if not equipment:
            raise serializers.ValidationError({
                "equipment": "Select equipment."
            })

        if equipment.tracking_type == "INDIVIDUAL":

            if not unit:
                raise serializers.ValidationError({
                    "equipment_unit": (
                        "Select the specific equipment unit."
                    )
                })

            if unit.equipment_id != equipment.id:
                raise serializers.ValidationError({
                    "equipment_unit": (
                        "This unit does not belong to the selected equipment."
                    )
                })

            if quantity != 1:
                raise serializers.ValidationError({
                    "quantity": (
                        "Individual equipment must have a quantity of 1."
                    )
                })

        elif equipment.tracking_type == "QUANTITY":

            if unit:
                raise serializers.ValidationError({
                    "equipment_unit": (
                        "Do not select an individual unit for quantity-based equipment."
                    )
                })

        return attrs


class BookingSerializer(serializers.ModelSerializer):

    items = BookingItemSerializer(many=True)

    class Meta:
        model = Booking

        fields = "__all__"

        read_only_fields = (
            "id",
            "booking_number",
            "status",
            "subtotal",
            "total_amount",
            "created_by",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):

        start_date = attrs.get("start_date")
        expected_return_date = attrs.get(
            "expected_return_date"
        )

        if (
            start_date
            and expected_return_date
            and expected_return_date <= start_date
        ):
            raise serializers.ValidationError({
                "expected_return_date": (
                    "Return date must be later than the start date."
                )
            })

        transport_required = attrs.get(
            "transport_required",
            False
        )

        transport_charge = attrs.get(
            "transport_charge",
            Decimal("0.00")
        )

        if not transport_required and transport_charge > 0:
            raise serializers.ValidationError({
                "transport_charge": (
                    "Transport charge cannot be added when transport is not requested."
                )
            })

        if transport_required and transport_charge <= 0:
            raise serializers.ValidationError({
                "transport_charge": (
                    "Enter the transport charge when transport is requested."
                )
            })

        items = attrs.get("items")

        if not items:
            raise serializers.ValidationError({
                "items": "A booking must contain at least one equipment item."
            })

        return attrs

    def create(self, validated_data):

        items_data = validated_data.pop("items")

        subtotal = Decimal("0.00")

        for item in items_data:
            line_total = (
                item["hire_rate"]
                * item.get("duration_units", 1)
                * item.get("quantity", 1)
            )

            item["line_total"] = line_total
            subtotal += line_total

        transport_charge = validated_data.get(
            "transport_charge",
            Decimal("0.00")
        )

        booking = Booking.objects.create(
            booking_number=(
                f"BKG-{timezone.now():%Y%m%d}-"
                f"{uuid4().hex[:8].upper()}"
            ),
            subtotal=subtotal,
            total_amount=subtotal + transport_charge,
            **validated_data
        )

        for item_data in items_data:
            BookingItem.objects.create(
                booking=booking,
                **item_data
            )

        # Credit requests automatically require an approval record.
        if booking.payment_arrangement == Booking.PaymentArrangement.CREDIT:
            CreditApproval.objects.create(
                booking=booking
            )

        return booking


class CreditApprovalSerializer(serializers.ModelSerializer):

    booking_number = serializers.CharField(
        source="booking.booking_number",
        read_only=True
    )

    reviewed_by = serializers.StringRelatedField(
        read_only=True
    )

    class Meta:
        model = CreditApproval

        fields = "__all__"

        read_only_fields = (
            "id",
            "booking",
            "status",
            "requested_at",
            "reviewed_by",
            "reviewed_at",
        )


class ReturnItemSerializer(serializers.ModelSerializer):

    equipment_name = serializers.CharField(
        source="booking_item.equipment.name",
        read_only=True
    )

    class Meta:
        model = ReturnItem

        fields = "__all__"

        read_only_fields = ("id",)


class BookingReturnSerializer(serializers.ModelSerializer):

    items = ReturnItemSerializer(many=True)

    class Meta:
        model = BookingReturn

        fields = "__all__"

        read_only_fields = (
            "id",
            "received_by",
            "created_at",
        )

    def validate(self, attrs):

        items = attrs.get("items")

        if not items:
            raise serializers.ValidationError({
                "items": "A return must contain at least one item."
            })

        return attrs

    def create(self, validated_data):

        items_data = validated_data.pop("items")

        booking_return = BookingReturn.objects.create(
            **validated_data
        )

        for item_data in items_data:
            ReturnItem.objects.create(
                booking_return=booking_return,
                **item_data
            )

        return booking_return


from decimal import Decimal
from uuid import uuid4

from django.db import models
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

    class Meta:
        model = BookingItem
        fields = [
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
        ]

        read_only_fields = [
            "id",
            "hire_rate",
            "line_total",
        ]

    def validate(self, attrs):
        equipment = attrs.get("equipment")
        equipment_unit = attrs.get("equipment_unit")
        quantity = attrs.get("quantity", 1)
        rate_period = attrs.get("rate_period")
        duration_units = attrs.get("duration_units", 1)

        if not equipment.is_active:
            raise serializers.ValidationError({
                "equipment": "This equipment is inactive."
            })

        if quantity < 1:
            raise serializers.ValidationError({
                "quantity": "Quantity must be at least 1."
            })

        if duration_units < 1:
            raise serializers.ValidationError({
                "duration_units": "Duration must be at least 1."
            })

        # Individual equipment validation
        if equipment.tracking_type == "INDIVIDUAL":

            if not equipment_unit:
                raise serializers.ValidationError({
                    "equipment_unit": "Select an individual equipment unit."
                })

            if equipment_unit.equipment_id != equipment.id:
                raise serializers.ValidationError({
                    "equipment_unit": "This unit does not belong to the selected equipment."
                })

            if quantity != 1:
                raise serializers.ValidationError({
                    "quantity": "Individual equipment quantity must be 1."
                })

            if equipment_unit.status != "AVAILABLE":
                raise serializers.ValidationError({
                    "equipment_unit": "This equipment unit is not currently available."
                })

        # Quantity-based equipment validation
        elif equipment.tracking_type == "QUANTITY":

            if equipment_unit:
                raise serializers.ValidationError({
                    "equipment_unit": "Quantity-based equipment cannot use individual units."
                })

            if quantity > equipment.available_quantity:
                raise serializers.ValidationError({
                    "quantity": (
                        f"Only {equipment.available_quantity} units "
                        "are currently available."
                    )
                })

        # Calculate the correct rate for both tracking types
        rate_field = f"{rate_period.lower()}_rate"
        actual_rate = getattr(equipment, rate_field, None)

        if actual_rate is None or actual_rate <= 0:
            raise serializers.ValidationError({
                "rate_period": "The selected hire rate is not configured for this equipment."
            })

        attrs["hire_rate"] = actual_rate

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

        read_only_fields = [
            "id",
        ]

    def validate_quantity_returned(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "Returned quantity must be at least 1."
            )

        return value

    def validate_damage_charge(self, value):
        if value < Decimal("0.00"):
            raise serializers.ValidationError(
                "Damage charge cannot be negative."
            )

        return value



class BookingReturnSerializer(serializers.ModelSerializer):

    items = ReturnItemSerializer(many=True)

    class Meta:
        model = BookingReturn
        fields = "__all__"

        read_only_fields = [
            "id",
            "received_by",
            "created_at",
        ]

    def validate(self, attrs):

        booking = attrs.get("booking")
        items = attrs.get("items")

        if not items:
            raise serializers.ValidationError({
                "items": "A return must contain at least one item."
            })

        if booking.status not in [
            Booking.Status.ACTIVE,
            Booking.Status.OVERDUE,
        ]:
            raise serializers.ValidationError({
                "booking": "Only active or overdue bookings can be returned."
            })

        seen_items = set()

        for item_data in items:

            booking_item = item_data["booking_item"]
            quantity = item_data["quantity_returned"]

            if booking_item.booking_id != booking.id:
                raise serializers.ValidationError({
                    "items": (
                        f"{booking_item.equipment.name} does not belong "
                        "to this booking."
                    )
                })

            if booking_item.id in seen_items:
                raise serializers.ValidationError({
                    "items": "An equipment item cannot appear twice in one return."
                })

            seen_items.add(booking_item.id)

            previous_returns = ReturnItem.objects.filter(
                booking_item=booking_item
            ).aggregate(
                total=models.Sum("quantity_returned")
            )["total"] or 0

            outstanding = booking_item.quantity - previous_returns

            if quantity > outstanding:
                raise serializers.ValidationError({
                    "items": (
                        f"Only {outstanding} units of "
                        f"{booking_item.equipment.name} remain outstanding."
                    )
                })

            if booking_item.equipment.tracking_type == "INDIVIDUAL":
                if quantity != 1:
                    raise serializers.ValidationError({
                        "items": "Individual equipment must be returned one unit at a time."
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

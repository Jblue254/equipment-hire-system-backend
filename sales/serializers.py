from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from inventory.models import Material
from .models import Sale, SaleItem, SaleCreditApproval

class SaleItemSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(
        source="material.name",
        read_only=True
    )

    unit = serializers.CharField(
        source="material.unit",
        read_only=True
    )

    class Meta:
        model = SaleItem
        fields = (
            "id",
            "material",
            "material_name",
            "unit",
            "quantity",
            "unit_price",
            "line_total",
        )
        read_only_fields = (
            "id",
            "unit_price",
            "line_total",
        )

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Quantity must be greater than zero."
            )
        return value

    def validate_material(self, value):
        if not value.is_active:
            raise serializers.ValidationError(
                "This material is inactive."
            )
        return value


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)

    created_by_name = serializers.CharField(
        source="created_by.username",
        read_only=True
    )

    class Meta:
        model = Sale
        fields = (
            "id",
            "sale_number",
            "customer_name",
            "customer_phone",
            "customer_email",
            "customer_address",
            "status",
            "payment_arrangement",
            "transport_required",
            "transport_charge",
            "subtotal",
            "total_amount",
            "items",
            "notes",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "sale_number",
            "status",
            "subtotal",
            "total_amount",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        items = attrs.get("items")

        if not items:
            raise serializers.ValidationError({
                "items": "A sale must contain at least one material."
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
                    "Transport charge cannot be added when "
                    "transport is not required."
                )
            })

        if transport_required and transport_charge <= 0:
            raise serializers.ValidationError({
                "transport_charge": (
                    "Enter a valid transport charge."
                )
            })

        material_ids = [
            item["material"].id for item in items
        ]

        if len(material_ids) != len(set(material_ids)):
            raise serializers.ValidationError({
                "items": "A material can only appear once in a sale."
            })

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")

        subtotal = Decimal("0.00")

        for item_data in items_data:
            material = item_data["material"]
            quantity = item_data["quantity"]

            unit_price = material.selling_price
            line_total = quantity * unit_price

            subtotal += line_total

            item_data["unit_price"] = unit_price
            item_data["line_total"] = line_total

        transport_charge = validated_data.get(
            "transport_charge",
            Decimal("0.00")
        )

        sale = Sale.objects.create(
            **validated_data,
            subtotal=subtotal,
            total_amount=subtotal + transport_charge,
        )

        for item_data in items_data:
            SaleItem.objects.create(
                sale=sale,
                **item_data
            )

        # Automatically create a credit approval request.
        if sale.payment_arrangement == Sale.PaymentArrangement.CREDIT:
            SaleCreditApproval.objects.create(
                sale=sale
            )

        return sale


    

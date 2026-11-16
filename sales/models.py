
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid


class Sale(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        READY = "READY", "Ready for Collection"
        DISPATCHED = "DISPATCHED", "Dispatched"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    class PaymentArrangement(models.TextChoices):
        FULL_PAYMENT = "FULL_PAYMENT", "Full Payment"
        CREDIT = "CREDIT", "Credit"

    sale_number = models.CharField(
        max_length=30,
        unique=True,
        editable=False
    )

    customer_name = models.CharField(max_length=150)
    customer_phone = models.CharField(max_length=20)
    customer_email = models.EmailField(blank=True)
    customer_address = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    payment_arrangement = models.CharField(
        max_length=20,
        choices=PaymentArrangement.choices,
        default=PaymentArrangement.FULL_PAYMENT
    )

    transport_required = models.BooleanField(default=False)
    transport_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))]
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sales_created"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.sale_number:
            self.sale_number = (
                f"SALE-{uuid.uuid4().hex[:10].upper()}"
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.sale_number


class SaleItem(models.Model):

    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="items"
    )

    material = models.ForeignKey(
        "inventory.Material",
        on_delete=models.PROTECT,
        related_name="sale_items"
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))]
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))]
    )

    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    def save(self, *args, **kwargs):
        self.line_total = self.quantity * self.unit_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.material.name} - {self.sale.sale_number}"


from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator


class Booking(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending Approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        READY_FOR_DISPATCH = "READY_FOR_DISPATCH", "Ready for Dispatch"
        ACTIVE = "ACTIVE", "Active Hire"
        OVERDUE = "OVERDUE", "Overdue"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    class PaymentArrangement(models.TextChoices):
        FULL_PAYMENT = "FULL_PAYMENT", "Full Payment"
        CREDIT = "CREDIT", "Credit"

    # Customer information
    customer_name = models.CharField(max_length=150)
    customer_phone = models.CharField(max_length=20)
    customer_email = models.EmailField(blank=True)
    customer_address = models.TextField(blank=True)

    # Booking information
    booking_number = models.CharField(
        max_length=30,
        unique=True
    )

    start_date = models.DateTimeField()
    expected_return_date = models.DateTimeField()

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING
    )

    payment_arrangement = models.CharField(
        max_length=20,
        choices=PaymentArrangement.choices,
        default=PaymentArrangement.FULL_PAYMENT
    )

    # Transport
    transport_required = models.BooleanField(default=False)

    transport_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )

    # Financial totals
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_bookings"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.booking_number} - {self.customer_name}"


class BookingItem(models.Model):

    class RatePeriod(models.TextChoices):
        HOURLY = "HOURLY", "Hourly"
        DAILY = "DAILY", "Daily"
        WEEKLY = "WEEKLY", "Weekly"
        MONTHLY = "MONTHLY", "Monthly"

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="items"
    )

    equipment = models.ForeignKey(
        "inventory.Equipment",
        on_delete=models.PROTECT,
        related_name="booking_items"
    )

    equipment_unit = models.ForeignKey(
        "inventory.EquipmentUnit",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="booking_items"
    )

    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )

    rate_period = models.CharField(
        max_length=20,
        choices=RatePeriod.choices
    )

    # Preserve the agreed rate even if equipment rates change later.
    hire_rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    duration_units = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )

    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.equipment.name} - {self.booking.booking_number}"


class CreditApproval(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name="credit_approval"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    requested_at = models.DateTimeField(auto_now_add=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_credit_requests"
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    reason = models.TextField(blank=True)

    review_notes = models.TextField(blank=True)

    def __str__(self):
        return f"Credit - {self.booking.booking_number} - {self.status}"


class BookingReturn(models.Model):

    booking = models.ForeignKey(
        Booking,
        on_delete=models.PROTECT,
        related_name="returns"
    )

    return_date = models.DateTimeField()

    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="received_returns"
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Return - {self.booking.booking_number}"


class ReturnItem(models.Model):

    class Condition(models.TextChoices):
        GOOD = "GOOD", "Good Condition"
        DAMAGED = "DAMAGED", "Damaged"
        MISSING = "MISSING", "Missing"

    booking_return = models.ForeignKey(
        BookingReturn,
        on_delete=models.CASCADE,
        related_name="items"
    )

    booking_item = models.ForeignKey(
        BookingItem,
        on_delete=models.PROTECT,
        related_name="return_items"
    )

    quantity_returned = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )

    condition = models.CharField(
        max_length=20,
        choices=Condition.choices,
        default=Condition.GOOD
    )

    damage_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )

    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.booking_item.equipment.name} - {self.condition}"

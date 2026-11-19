
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Lorry(models.Model):

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        ON_TRIP = "ON_TRIP", "On Trip"
        UNDER_MAINTENANCE = "UNDER_MAINTENANCE", "Under Maintenance"
        INACTIVE = "INACTIVE", "Inactive"

    registration_number = models.CharField(
        max_length=30,
        unique=True
    )

    make = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)

    capacity_tonnes = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))]
    )

    status = models.CharField(
        max_length=25,
        choices=Status.choices,
        default=Status.AVAILABLE
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.registration_number


class Driver(models.Model):

    full_name = models.CharField(max_length=150)

    phone_number = models.CharField(max_length=20)

    licence_number = models.CharField(
        max_length=50,
        unique=True
    )

    licence_expiry_date = models.DateField(
        null=True,
        blank=True
    )

    is_active = models.BooleanField(default=True)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name


class Trip(models.Model):

    class Meta:
    
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(booking__isnull=False, sale__isnull=True)
                    | models.Q(booking__isnull=True, sale__isnull=False)
                ),
                name="trip_booking_or_sale_only",
            )
        ]

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    lorry = models.ForeignKey(
        Lorry,
        on_delete=models.PROTECT,
        related_name="trips"
    )

    driver = models.ForeignKey(
        Driver,
        on_delete=models.PROTECT,
        related_name="trips"
    )

    booking = models.OneToOneField(
        "bookings.Booking",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transport_trip"
    )

    sale = models.OneToOneField(
        "sales.Sale",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transport_trip"
    )

    pickup_location = models.TextField()
    destination = models.TextField()

    distance_km = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))]
    )

    transport_charge = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))]
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    scheduled_at = models.DateTimeField(
        null=True,
        blank=True
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    notes = models.TextField(blank=True)

    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="trips_assigned"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        from django.core.exceptions import ValidationError

        if bool(self.booking_id) == bool(self.sale_id):
            raise ValidationError(
                "A trip must belong to either a booking or a sale, not both."
            )

    def __str__(self):
        return f"Trip {self.id} - {self.lorry.registration_number}"



class TripExpense(models.Model):

    class ExpenseType(models.TextChoices):
        FUEL = "FUEL", "Fuel"
        PARKING = "PARKING", "Parking"
        TOLL = "TOLL", "Toll Charges"
        OTHER = "OTHER", "Other"

    trip = models.ForeignKey(
        Trip,
        on_delete=models.PROTECT,
        related_name="expenses"
    )

    expense_type = models.CharField(
        max_length=20,
        choices=ExpenseType.choices
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))]
    )

    description = models.TextField(blank=True)
    expense_date = models.DateField()

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="trip_expenses"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Trip {self.trip_id} - {self.expense_type} - {self.amount}"


class LorryExpense(models.Model):

    class ExpenseType(models.TextChoices):
        FUEL = "FUEL", "Fuel"
        REPAIR = "REPAIR", "Repair"
        SERVICE = "SERVICE", "Routine Servicing"
        TYRES = "TYRES", "Tyres"
        INSURANCE = "INSURANCE", "Insurance"
        LICENCE = "LICENCE", "Licence and Inspection"
        OTHER = "OTHER", "Other"

    lorry = models.ForeignKey(
        Lorry,
        on_delete=models.PROTECT,
        related_name="expenses"
    )

    expense_type = models.CharField(
        max_length=20,
        choices=ExpenseType.choices
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))]
    )

    description = models.TextField(blank=True)
    expense_date = models.DateField()

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="lorry_expenses"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.lorry.registration_number} - {self.expense_type} - {self.amount}"

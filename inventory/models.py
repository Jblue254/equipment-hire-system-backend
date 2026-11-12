from django.db import models
from django.conf import settings



class EquipmentCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Equipment(models.Model):

    class TrackingType(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "Individual"
        QUANTITY = "QUANTITY", "Quantity-based"

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        RESERVED = "RESERVED", "Reserved"
        HIRED_OUT = "HIRED_OUT", "Hired Out"
        UNDER_MAINTENANCE = "UNDER_MAINTENANCE", "Under Maintenance"
        DAMAGED = "DAMAGED", "Damaged"
        RETIRED = "RETIRED", "Retired"

    category = models.ForeignKey(
        EquipmentCategory,
        on_delete=models.PROTECT,
        related_name="equipment"
    )

    name = models.CharField(max_length=150)

    tracking_type = models.CharField(
        max_length=20,
        choices=TrackingType.choices
    )

    identification_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True
    )

    total_quantity = models.PositiveIntegerField(default=1)

    available_quantity = models.PositiveIntegerField(default=1)

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.AVAILABLE
    )

    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    daily_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    weekly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    monthly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    description = models.TextField(blank=True)

    condition_notes = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class MaterialCategory(models.Model):

    name = models.CharField(max_length=100, unique=True)

    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Material(models.Model):

    class Unit(models.TextChoices):
        TONNE = "TONNE", "Tonne"
        TRIP = "TRIP", "Trip"
        LORRY_LOAD = "LORRY_LOAD", "Lorry Load"
        CUBIC_METRE = "CUBIC_METRE", "Cubic Metre"
        BAG = "BAG", "Bag"
        PIECE = "PIECE", "Piece"

    category = models.ForeignKey(
        MaterialCategory,
        on_delete=models.PROTECT,
        related_name="materials"
    )

    name = models.CharField(max_length=150)

    unit = models.CharField(
        max_length=20,
        choices=Unit.choices
    )

    stock_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    reorder_level = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    buying_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    selling_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class StockMovement(models.Model):

    class MovementType(models.TextChoices):
        STOCK_IN = "STOCK_IN", "Stock In"
        STOCK_OUT = "STOCK_OUT", "Stock Out"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"

    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name="stock_movements"
    )

    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    reference = models.CharField(
        max_length=100,
        blank=True
    )

    notes = models.TextField(blank=True)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.material.name} - {self.movement_type}"

class EquipmentUnit(models.Model):

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        RESERVED = "RESERVED", "Reserved"
        HIRED_OUT = "HIRED_OUT", "Hired Out"
        UNDER_MAINTENANCE = "UNDER_MAINTENANCE", "Under Maintenance"
        DAMAGED = "DAMAGED", "Damaged"
        RETIRED = "RETIRED", "Retired"

    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.PROTECT,
        related_name="units"
    )

    asset_number = models.CharField(
        max_length=100,
        unique=True
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.AVAILABLE
    )

    condition_notes = models.TextField(blank=True)

    date_acquired = models.DateField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.equipment.name} - {self.asset_number}"

class MaintenanceRecord(models.Model):

    class MaintenanceType(models.TextChoices):
        REPAIR = "REPAIR", "Repair"
        ROUTINE_SERVICE = "ROUTINE_SERVICE", "Routine Service"
        INSPECTION = "INSPECTION", "Inspection"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        REPORTED = "REPORTED", "Reported"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.PROTECT,
        related_name="maintenance_records"
    )

    unit = models.ForeignKey(
        EquipmentUnit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="maintenance_records"
    )

    maintenance_type = models.CharField(
        max_length=30,
        choices=MaintenanceType.choices
    )

    problem_reported = models.TextField()

    work_done = models.TextField(blank=True)

    service_provider = models.CharField(
        max_length=150,
        blank=True
    )

    repair_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    date_reported = models.DateField(auto_now_add=True)

    date_started = models.DateField(
        null=True,
        blank=True
    )

    date_completed = models.DateField(
        null=True,
        blank=True
    )

    next_service_date = models.DateField(
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REPORTED
    )

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="maintenance_records"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.equipment.name} - {self.maintenance_type}"
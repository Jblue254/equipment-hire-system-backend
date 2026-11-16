
from django.conf import settings
from django.db import models


class Notification(models.Model):

    class NotificationType(models.TextChoices):
        BOOKING = "BOOKING", "Booking"
        CREDIT = "CREDIT", "Credit Approval"
        SALE = "SALE", "Sale"
        PAYMENT = "PAYMENT", "Payment"
        EQUIPMENT = "EQUIPMENT", "Equipment"
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        LOW_STOCK = "LOW_STOCK", "Low Stock"
        OVERDUE = "OVERDUE", "Overdue Equipment"
        TRANSPORT = "TRANSPORT", "Transport"
        SYSTEM = "SYSTEM", "System"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications"
    )

    title = models.CharField(max_length=200)

    message = models.TextField()

    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM
    )

    related_object_type = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    related_object_id = models.PositiveIntegerField(
        blank=True,
        null=True
    )

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.recipient}"

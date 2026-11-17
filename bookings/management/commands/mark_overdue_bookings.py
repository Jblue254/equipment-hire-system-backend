
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from notifications.models import Notification
from notifications.services import notify_users
from notifications.utils import get_notification_recipients


class Command(BaseCommand):
    help = "Automatically mark overdue bookings."

    def handle(self, *args, **options):
        today = timezone.localdate()

        with transaction.atomic():
            overdue_bookings = list(
                Booking.objects.select_for_update().filter(
                    status=Booking.Status.ACTIVE,
                    expected_return_date__lt=today
                )
            )

            if not overdue_bookings:
                self.stdout.write(
                    self.style.SUCCESS(
                        "Successfully marked 0 booking(s) as overdue."
                    )
                )
                return

            recipients = get_notification_recipients()
            updated_count = 0

            for booking in overdue_bookings:
                booking.status = Booking.Status.OVERDUE
                booking.save(update_fields=["status", "updated_at"])

                notify_users(
                    recipients,
                    title="Booking Overdue",
                    message=(
                        f"Booking {booking.booking_number} for "
                        f"{booking.customer_name} is overdue. "
                        f"Expected return date was "
                        f"{booking.expected_return_date}."
                    ),
                    notification_type=Notification.NotificationType.OVERDUE,
                    related_object_type="booking",
                    related_object_id=booking.id,
                )

                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully marked {updated_count} booking(s) as overdue."
            )
        )

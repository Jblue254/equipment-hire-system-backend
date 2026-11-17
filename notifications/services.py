
from .models import Notification


def create_notification(
    recipient,
    title,
    message,
    notification_type=Notification.NotificationType.SYSTEM,
    related_object_type=None,
    related_object_id=None,
):
    return Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        notification_type=notification_type,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
    )


def notify_users(
    users,
    title,
    message,
    notification_type=Notification.NotificationType.SYSTEM,
    related_object_type=None,
    related_object_id=None,
):
    notifications = [
        Notification(
            recipient=user,
            title=title,
            message=message,
            notification_type=notification_type,
            related_object_type=related_object_type,
            related_object_id=related_object_id,
        )
        for user in users
    ]

    return Notification.objects.bulk_create(notifications)

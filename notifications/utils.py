from django.contrib.auth import get_user_model


User = get_user_model()


def get_notification_recipients():
    """
    Return active Admin and Storekeeper users.
    """

    return User.objects.filter(
        is_active=True,
        role__in=[
            User.Role.ADMIN,
            User.Role.STOREKEEPER,
        ]
    )

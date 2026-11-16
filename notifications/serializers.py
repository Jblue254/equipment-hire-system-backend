
from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):

    recipient_name = serializers.CharField(
        source="recipient.username",
        read_only=True
    )

    class Meta:
        model = Notification
        fields = "__all__"
        read_only_fields = (
            "id",
            "recipient",
            "title",
            "message",
            "notification_type",
            "related_object_type",
            "related_object_id",
            "created_at",
        )

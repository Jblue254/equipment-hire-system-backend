
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from accounts.permissions import IsAdminOrStorekeeper
from .models import Notification
from .serializers import NotificationSerializer


class BaseNotificationView:
    permission_classes = [IsAuthenticated, IsAdminOrStorekeeper]


# -------------------------
# NOTIFICATION LIST
# -------------------------

class NotificationListView(
    BaseNotificationView,
    generics.ListAPIView
):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        queryset = Notification.objects.filter(
            recipient=self.request.user
        )

        unread = self.request.query_params.get("unread")
        notification_type = self.request.query_params.get("type")

        if unread is not None:
            queryset = queryset.filter(
                is_read=unread.lower() == "true"
            )

        if notification_type:
            queryset = queryset.filter(
                notification_type=notification_type.upper()
            )

        return queryset.order_by("-created_at")


# -------------------------
# UNREAD NOTIFICATION COUNT
# -------------------------

class UnreadNotificationCountView(
    BaseNotificationView,
    APIView
):

    def get(self, request):
        count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()

        return Response({
            "unread_count": count
        })


# -------------------------
# MARK ONE AS READ
# -------------------------

class MarkNotificationReadView(
    BaseNotificationView,
    APIView
):

    def post(self, request, pk):
        notification = get_object_or_404(
            Notification,
            pk=pk,
            recipient=request.user
        )

        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])

        return Response(
            NotificationSerializer(notification).data,
            status=status.HTTP_200_OK
        )


# -------------------------
# MARK ALL AS READ
# -------------------------

class MarkAllNotificationsReadView(
    BaseNotificationView,
    APIView
):

    def post(self, request):
        updated = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).update(is_read=True)

        return Response({
            "message": "All notifications marked as read.",
            "updated_count": updated
        })

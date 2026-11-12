
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsAdminRole, IsAdminOrStorekeeper

from .models import (
    Booking,
    CreditApproval,
)

from .serializers import (
    BookingSerializer,
    CreditApprovalSerializer,
)


class BaseBookingView:
    permission_classes = [
        IsAuthenticated,
        IsAdminOrStorekeeper,
    ]


# BOOKINGS

class BookingListCreateView(
    BaseBookingView,
    generics.ListCreateAPIView
):
    serializer_class = BookingSerializer

    queryset = Booking.objects.prefetch_related(
        "items",
        "items__equipment",
        "items__equipment_unit",
    ).select_related(
        "created_by"
    ).all()

    def get_queryset(self):
        queryset = super().get_queryset()

        booking_status = self.request.query_params.get("status")
        customer_phone = self.request.query_params.get("customer_phone")
        booking_number = self.request.query_params.get("booking_number")

        if booking_status:
            queryset = queryset.filter(status=booking_status)

        if customer_phone:
            queryset = queryset.filter(
                customer_phone__icontains=customer_phone
            )

        if booking_number:
            queryset = queryset.filter(
                booking_number__icontains=booking_number
            )

        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user
        )


class BookingDetailView(
    BaseBookingView,
    generics.RetrieveAPIView
):
    queryset = Booking.objects.prefetch_related(
        "items",
        "items__equipment",
        "items__equipment_unit",
        "returns",
    ).select_related(
        "created_by"
    ).all()

    serializer_class = BookingSerializer


# CREDIT REQUESTS

class CreditApprovalListView(
    BaseBookingView,
    generics.ListAPIView
):
    serializer_class = CreditApprovalSerializer

    queryset = CreditApproval.objects.select_related(
        "booking",
        "reviewed_by",
    ).all()

    def get_queryset(self):
        queryset = super().get_queryset()

        approval_status = self.request.query_params.get("status")

        if approval_status:
            queryset = queryset.filter(status=approval_status)

        return queryset


class CreditApprovalDecisionView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsAdminRole,
    ]

    @transaction.atomic
    def post(self, request, pk):

        approval = get_object_or_404(
            CreditApproval.objects.select_for_update().select_related(
                "booking"
            ),
            pk=pk
        )

        if approval.status != CreditApproval.Status.PENDING:
            return Response(
                {
                    "error": "This credit request has already been reviewed."
                },
                status=400
            )

        decision = request.data.get("decision")
        review_notes = request.data.get("review_notes", "")

        if decision not in ["APPROVED", "REJECTED"]:
            return Response(
                {
                    "error": "Decision must be APPROVED or REJECTED."
                },
                status=400
            )

        approval.status = decision
        approval.reviewed_by = request.user
        approval.reviewed_at = timezone.now()
        approval.review_notes = review_notes

        approval.save(update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "review_notes",
        ])

        booking = approval.booking

        if decision == "APPROVED":
            booking.status = Booking.Status.APPROVED

        else:
            booking.status = Booking.Status.REJECTED

        booking.save(update_fields=[
            "status",
            "updated_at",
        ])

        return Response({
            "message": f"Credit request {decision.lower()} successfully.",
            "booking_number": booking.booking_number,
            "approval_status": approval.status,
            "booking_status": booking.status,
            "reviewed_by": str(request.user),
        })

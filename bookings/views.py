
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from inventory.models import Equipment, EquipmentUnit
from inventory.views import sync_equipment_summary

from accounts.permissions import IsAdminRole, IsAdminOrStorekeeper

from .models import (
    Booking,
    CreditApproval,
)

from .serializers import (
    BookingSerializer,
    CreditApprovalSerializer,
)

def reserve_booking_equipment(booking):
    """
    Reserve all equipment requested in a booking.
    Must be called inside transaction.atomic().
    """

    items = booking.items.select_related(
        "equipment",
        "equipment_unit"
    ).all()

    reserved_units = set()

    for item in items:

        equipment = Equipment.objects.select_for_update().get(
            pk=item.equipment_id
        )

        if not equipment.is_active:
            raise serializers.ValidationError(
                f"{equipment.name} is inactive."
            )

        if equipment.tracking_type == "INDIVIDUAL":

            unit = EquipmentUnit.objects.select_for_update().get(
                pk=item.equipment_unit_id
            )

            if unit.equipment_id != equipment.id:
                raise serializers.ValidationError(
                    "The selected unit does not belong to this equipment."
                )

            if unit.status != EquipmentUnit.Status.AVAILABLE:
                raise serializers.ValidationError(
                    f"Unit {unit.asset_number} is no longer available."
                )

            if unit.pk in reserved_units:
                raise serializers.ValidationError(
                    f"Unit {unit.asset_number} appears more than once."
                )

            unit.status = EquipmentUnit.Status.RESERVED
            unit.save(update_fields=["status", "updated_at"])

            reserved_units.add(unit.pk)

            sync_equipment_summary(equipment)

        else:

            if item.equipment_unit_id:
                raise serializers.ValidationError(
                    "Quantity-based equipment cannot use individual units."
                )

            if item.quantity > equipment.available_quantity:
                raise serializers.ValidationError(
                    f"Only {equipment.available_quantity} units of "
                    f"{equipment.name} remain available."
                )

            equipment.available_quantity -= item.quantity

            equipment.save(update_fields=["available_quantity"])

            sync_equipment_summary(equipment)

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

class BookingDecisionView(APIView):
    permission_classes = [
        IsAuthenticated,
        IsAdminOrStorekeeper,
    ]

    @transaction.atomic
    def post(self, request, pk):

        booking = get_object_or_404(
            Booking.objects.select_for_update(),
            pk=pk
        )

        if booking.status != Booking.Status.PENDING:
            return Response(
                {"error": "This booking has already been reviewed."},
                status=400
            )

        if booking.payment_arrangement == Booking.PaymentArrangement.CREDIT:

            return Response(
                {
                    "error": (
                        "Credit bookings must be reviewed through "
                        "the Admin-only credit approval endpoint."
                    )
                },
                status=400
    )

        decision = request.data.get("decision")

        if decision == "APPROVE":

            try:
                reserve_booking_equipment(booking)

            except serializers.ValidationError as error:
                return Response(
                    {"error": error.detail},
                    status=400
                )

            booking.status = Booking.Status.APPROVED

        elif decision == "REJECT":

            booking.status = Booking.Status.REJECTED

        else:
            return Response(
                {"error": "Decision must be APPROVE or REJECT."},
                status=400
            )

        booking.save(update_fields=["status", "updated_at"])

        return Response({
            "message": f"Booking {decision.lower()}d successfully.",
            "booking_number": booking.booking_number,
            "status": booking.status
        })


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
                {"error": "This credit request has already been reviewed."},
                status=400
            )

        booking = Booking.objects.select_for_update().get(
            pk=approval.booking_id
        )

        if booking.payment_arrangement != Booking.PaymentArrangement.CREDIT:
            return Response(
                {"error": "This booking is not a credit booking."},
                status=400
            )

        decision = request.data.get("decision")
        review_notes = request.data.get("review_notes", "")

        if decision not in ["APPROVED", "REJECTED"]:
            return Response(
                {"error": "Decision must be APPROVED or REJECTED."},
                status=400
            )

        if decision == "APPROVED":
            try:
                reserve_booking_equipment(booking)

            except serializers.ValidationError as error:
                transaction.set_rollback(True)
                return Response(
                    {"error": error.detail},
                    status=400
                )

            booking.status = Booking.Status.APPROVED

        else:
            booking.status = Booking.Status.REJECTED

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

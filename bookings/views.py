from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal
from django.db.models import Sum
from django.contrib.auth import get_user_model

from notifications.models import Notification
from notifications.services import notify_users
from notifications.utils import get_notification_recipients

User = get_user_model()

from finance.models import Payment
from rest_framework import generics, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from inventory.models import (
    Equipment,
    EquipmentUnit,
    MaintenanceRecord,
)
from inventory.views import sync_equipment_summary
from accounts.permissions import IsAdminRole, IsAdminOrStorekeeper
from .models import (
    Booking,
    BookingItem,
    BookingReturn,
    ReturnItem,
    CreditApproval,
    DispatchRecord,
)
from .serializers import (
    BookingSerializer,
    BookingReturnSerializer,
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
        booking = serializer.save(
            created_by=self.request.user
        )

        recipients = get_notification_recipients()

        # Notify Admin and Storekeeper about the new booking.
        notify_users(
            recipients,
            title="New Booking Received",
            message=(
                f"Booking {booking.booking_number} from "
                f"{booking.customer_name} is awaiting review."
            ),
            notification_type=Notification.NotificationType.BOOKING,
            related_object_type="booking",
            related_object_id=booking.id,
        )

        # Credit requests require Admin approval.
        if booking.payment_arrangement == Booking.PaymentArrangement.CREDIT:
            admin_recipients = recipients.filter(
                role=User.Role.ADMIN
            )

            notify_users(
                admin_recipients,
                title="Credit Approval Required",
                message=(
                    f"Booking {booking.booking_number} requires "
                    f"credit approval."
                ),
                notification_type=Notification.NotificationType.CREDIT,
                related_object_type="booking",
                related_object_id=booking.id,
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

        if booking.created_by:
            notify_users(
                [booking.created_by],
                title="Booking Decision",
                message=(
                    f"Booking {booking.booking_number} has been "
                    f"{booking.status.lower()}."
                ),
                notification_type=Notification.NotificationType.BOOKING,
                related_object_type="booking",
                related_object_id=booking.id,
            )

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

        if booking.created_by:

            notify_users(
                [booking.created_by],
                title="Credit Approval Decision",
                message=(
                    f"Credit request for booking {booking.booking_number} "
                    f"has been {approval.status.lower()}."
                ),
                notification_type=Notification.NotificationType.CREDIT,
                related_object_type="booking",
                related_object_id=booking.id,
            )

        return Response({
            "message": f"Credit request {decision.lower()} successfully.",
            "booking_number": booking.booking_number,
            "approval_status": approval.status,
            "booking_status": booking.status,
            "reviewed_by": str(request.user),
        })


class BookingDispatchView(APIView):
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

        if booking.status != Booking.Status.APPROVED:
            return Response(
                {"error": "Only approved bookings can be dispatched."},
                status=400
            )

        if DispatchRecord.objects.filter(booking=booking).exists():
            return Response(
                {"error": "This booking has already been dispatched."},
                status=400
            )

        # Check confirmed payments
        confirmed_amount = Payment.objects.filter(
            booking=booking,
            status=Payment.PaymentStatus.CONFIRMED
        ).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        fully_paid = confirmed_amount >= booking.total_amount

        # Check Admin-approved credit
        credit_approved = CreditApproval.objects.filter(
            booking=booking,
            status=CreditApproval.Status.APPROVED
        ).exists()

        if not fully_paid and not credit_approved:
            return Response(
                {
                    "error": (
                        "Dispatch requires full payment "
                        "or Admin-approved credit."
                    ),
                    "total_amount": str(booking.total_amount),
                    "confirmed_payments": str(confirmed_amount),
                    "outstanding_balance": str(
                        max(
                            booking.total_amount - confirmed_amount,
                            Decimal("0.00")
                        )
                    )
                },
                status=400
            )

        # Confirm that reserved individual units are still reserved
        items = booking.items.select_related(
            "equipment",
            "equipment_unit"
        ).all()

        for item in items:

            if item.equipment.tracking_type == "INDIVIDUAL":

                unit = EquipmentUnit.objects.select_for_update().get(
                    pk=item.equipment_unit_id
                )

                if unit.status != "RESERVED":
                    return Response(
                        {
                            "error": (
                                f"Equipment unit {unit.asset_number} "
                                "is not reserved for this booking."
                            )
                        },
                        status=400
                    )

                unit.status = "HIRED_OUT"
                unit.save(update_fields=["status", "updated_at"])

        # Create dispatch audit record
        dispatch = DispatchRecord.objects.create(
            booking=booking,
            dispatched_by=request.user,
            notes=request.data.get("notes", "")
        )

        # Update individual equipment summary records
        for item in items:
            if item.equipment.tracking_type == "INDIVIDUAL":
                sync_equipment_summary(item.equipment)

        booking.status = Booking.Status.ACTIVE
        booking.save(update_fields=["status", "updated_at"])


        notify_users(
            get_notification_recipients(),
            title="Equipment Dispatched",
            message=(
                f"Booking {booking.booking_number} for "
                f"{booking.customer_name} has been dispatched."
            ),
            notification_type=Notification.NotificationType.EQUIPMENT,
            related_object_type="booking",
            related_object_id=booking.id,
        )

        return Response({
            "message": "Equipment dispatched successfully.",
            "booking_number": booking.booking_number,
            "booking_status": booking.status,
            "dispatch_id": dispatch.id,
            "dispatched_by": request.user.username,
            "dispatched_at": dispatch.dispatched_at,
        }, status=200)


# BOOKING RETURNS

class BookingReturnListCreateView(
    BaseBookingView,
    generics.ListCreateAPIView
):
    serializer_class = BookingReturnSerializer

    def get_queryset(self):
        queryset = BookingReturn.objects.select_related(
            "booking",
            "received_by"
        ).prefetch_related(
            "items",
            "items__booking_item",
            "items__booking_item__equipment"
        )

        booking_id = self.request.query_params.get("booking")

        if booking_id:
            queryset = queryset.filter(booking_id=booking_id)

        return queryset

    @transaction.atomic
    def perform_create(self, serializer):

        booking_id = serializer.validated_data["booking"].pk

        # Lock the booking to prevent simultaneous return processing.
        booking = Booking.objects.select_for_update().get(
            pk=booking_id
        )

        if booking.status not in [
            Booking.Status.ACTIVE,
            Booking.Status.OVERDUE,
        ]:
            raise serializers.ValidationError({
                "booking": "Only active or overdue bookings can receive returns."
            })

        return_items = serializer.validated_data.get("items", [])

        if not return_items:
            raise serializers.ValidationError({
                "items": "At least one returned item is required."
            })

        # Lock the booking items and verify cumulative return quantities.
        booking_items = {
            item.pk: item
            for item in BookingItem.objects.select_for_update().filter(
                booking=booking
            )
        }

        for return_data in return_items:

            booking_item = return_data["booking_item"]
            quantity = return_data["quantity_returned"]

            if booking_item.pk not in booking_items:
                raise serializers.ValidationError({
                    "items": "An item does not belong to this booking."
                })

            previous_quantity = (
                ReturnItem.objects.filter(
                    booking_item=booking_item
                ).aggregate(
                    total=Sum("quantity_returned")
                )["total"] or 0
            )

            if previous_quantity + quantity > booking_item.quantity:
                raise serializers.ValidationError({
                    "items": (
                        f"Return quantity exceeds the outstanding "
                        f"quantity for {booking_item.equipment.name}."
                    )
                })

            equipment = booking_item.equipment

            if equipment.tracking_type == "INDIVIDUAL":

                if quantity != 1:
                    raise serializers.ValidationError({
                        "quantity_returned": (
                            "Individual equipment must be returned one unit at a time."
                        )
                    })

                unit = EquipmentUnit.objects.select_for_update().get(
                    pk=booking_item.equipment_unit_id
                )

                if unit.status != EquipmentUnit.Status.HIRED_OUT:
                    raise serializers.ValidationError({
                        "equipment_unit": (
                            f"Unit {unit.asset_number} is not currently hired out."
                        )
                    })

        # Create the return and its nested return items.
        booking_return = serializer.save(
            received_by=self.request.user
        )


        # Update equipment condition and availability.
        affected_equipment = {}


        good_returns = []
        damaged_returns = []
        missing_returns = []


        for returned_item in booking_return.items.select_related(
            "booking_item",
            "booking_item__equipment",
            "booking_item__equipment_unit"
        ):

            booking_item = returned_item.booking_item
            equipment = Equipment.objects.select_for_update().get(
                pk=booking_item.equipment_id
            )

            affected_equipment[equipment.pk] = equipment

            if returned_item.condition == ReturnItem.Condition.MISSING:

                missing_returns.append(
                    f"{equipment.name} (quantity: {returned_item.quantity_returned})"
                )

                if equipment.tracking_type == "INDIVIDUAL":
                    unit = EquipmentUnit.objects.select_for_update().get(
                        pk=booking_item.equipment_unit_id
                    )

                    unit.status = EquipmentUnit.Status.LOST
                    unit.condition_notes = (
                        returned_item.notes or "Equipment declared missing."
                    )

                    unit.save(update_fields=[
                        "status",
                        "condition_notes",
                        "updated_at"
                    ])

                # Missing quantity-based equipment remains unavailable.
                continue

            if equipment.tracking_type == "INDIVIDUAL":

                unit = EquipmentUnit.objects.select_for_update().get(
                    pk=booking_item.equipment_unit_id
                )

                if returned_item.condition == ReturnItem.Condition.GOOD:
                    good_returns.append(
                        f"{equipment.name} (quantity: {returned_item.quantity_returned})"
                    )
                    unit.status = EquipmentUnit.Status.AVAILABLE

                elif returned_item.condition == ReturnItem.Condition.DAMAGED:
                    damaged_returns.append(
                        f"{equipment.name} (quantity: {returned_item.quantity_returned})"
                    )
                    unit.status = EquipmentUnit.Status.UNDER_MAINTENANCE

                    MaintenanceRecord.objects.create(
                        equipment=equipment,
                        unit=unit,
                        quantity_affected=1,
                        maintenance_type=MaintenanceRecord.MaintenanceType.REPAIR,
                        problem_reported=(
                            returned_item.notes
                            or "Equipment returned in damaged condition."
                        ),
                        recorded_by=self.request.user,
                        condition_cleared=False,
                    )

                unit.save(update_fields=[
                    "status",
                    "updated_at"
                ])

            else:
                if returned_item.condition == ReturnItem.Condition.GOOD:
                    good_returns.append(
                        f"{equipment.name} (quantity: {returned_item.quantity_returned})"
                    )

                    equipment.available_quantity += (
                        returned_item.quantity_returned
                    )

                elif returned_item.condition == ReturnItem.Condition.DAMAGED:
                    damaged_returns.append(
                        f"{equipment.name} (quantity: {returned_item.quantity_returned})"
                    )

                    # Damaged quantity remains unavailable.
                    MaintenanceRecord.objects.create(
                        equipment=equipment,
                        quantity_affected=returned_item.quantity_returned,
                        maintenance_type=MaintenanceRecord.MaintenanceType.REPAIR,
                        problem_reported=(
                            returned_item.notes
                            or "Equipment returned in damaged condition."
                        ),
                        recorded_by=self.request.user,
                        condition_cleared=False,
                    )

        # Synchronize equipment summary records.
        for equipment in affected_equipment.values():
            sync_equipment_summary(equipment)

        # Send return notifications once, after processing all items.
        recipients = get_notification_recipients()

        if good_returns:
            notify_users(
                recipients,
                title="Equipment Returned",
                message=(
                    f"Booking {booking.booking_number}: "
                    f"Good condition: {', '.join(good_returns)}."
                ),
                notification_type=Notification.NotificationType.EQUIPMENT,
                related_object_type="booking",
                related_object_id=booking.id,
            )

        if damaged_returns:
            notify_users(
                recipients,
                title="Damaged Equipment Returned",
                message=(
                    f"Booking {booking.booking_number}: "
                    f"{', '.join(damaged_returns)}. "
                    "Maintenance attention is required."
                ),
                notification_type=Notification.NotificationType.MAINTENANCE,
                related_object_type="booking",
                related_object_id=booking.id,
            )

        if missing_returns:
            notify_users(
                recipients,
                title="Missing Equipment Reported",
                message=(
                    f"Booking {booking.booking_number}: "
                    f"{', '.join(missing_returns)} reported missing."
                ),
                notification_type=Notification.NotificationType.EQUIPMENT,
                related_object_type="booking",
                related_object_id=booking.id,
            )

        # Complete the booking when every booked quantity has
        # been returned or recorded as missing.
        all_accounted_for = True

        for booking_item in booking.items.all():

            accounted_quantity = (
                ReturnItem.objects.filter(
                    booking_item=booking_item
                ).aggregate(
                    total=Sum("quantity_returned")
                )["total"] or 0
            )

            if accounted_quantity < booking_item.quantity:
                all_accounted_for = False
                break

        if all_accounted_for:
            booking.status = Booking.Status.COMPLETED
            booking.save(update_fields=[
                "status",
                "updated_at"
            ])

            notify_users(
                recipients,
                title="Booking Completed",
                message=(
                    f"All equipment for booking "
                    f"{booking.booking_number} has been accounted for."
                ),
                notification_type=Notification.NotificationType.BOOKING,
                related_object_type="booking",
                related_object_id=booking.id,
            )
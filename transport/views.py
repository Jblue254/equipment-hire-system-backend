
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminOrStorekeeper

from .models import Lorry, Driver, Trip, TripExpense, LorryExpense
from .serializers import (
    LorrySerializer,
    DriverSerializer,
    TripSerializer,
    TripExpenseSerializer,
    LorryExpenseSerializer,
)


ACTIVE_TRIP_STATUSES = [
    Trip.Status.PENDING,
    Trip.Status.ASSIGNED,
    Trip.Status.IN_PROGRESS,
]


class BaseTransportView:
    permission_classes = [IsAdminOrStorekeeper]


# -------------------------
# LORRY MANAGEMENT
# -------------------------

class LorryListCreateView(BaseTransportView, generics.ListCreateAPIView):
    serializer_class = LorrySerializer
    queryset = Lorry.objects.all().order_by("-created_at")

    def get_queryset(self):
        queryset = super().get_queryset()

        search = self.request.query_params.get("search")
        status_filter = self.request.query_params.get("status")

        if search:
            queryset = queryset.filter(
                Q(registration_number__icontains=search)
                | Q(make__icontains=search)
                | Q(model__icontains=search)
            )

        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())

        return queryset


class LorryDetailView(BaseTransportView, generics.RetrieveUpdateAPIView):
    serializer_class = LorrySerializer
    queryset = Lorry.objects.all()


# -------------------------
# DRIVER MANAGEMENT
# -------------------------

class DriverListCreateView(BaseTransportView, generics.ListCreateAPIView):
    serializer_class = DriverSerializer
    queryset = Driver.objects.all().order_by("-created_at")

    def get_queryset(self):
        queryset = super().get_queryset()

        search = self.request.query_params.get("search")
        active = self.request.query_params.get("active")

        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search)
                | Q(phone_number__icontains=search)
                | Q(licence_number__icontains=search)
            )

        if active is not None:
            queryset = queryset.filter(
                is_active=active.lower() == "true"
            )

        return queryset


class DriverDetailView(BaseTransportView, generics.RetrieveUpdateAPIView):
    serializer_class = DriverSerializer
    queryset = Driver.objects.all()


# -------------------------
# TRIP MANAGEMENT
# -------------------------

class TripListCreateView(BaseTransportView, generics.ListCreateAPIView):
    serializer_class = TripSerializer
    queryset = Trip.objects.select_related(
        "lorry", "driver", "booking", "sale"
    ).order_by("-created_at")

    def get_queryset(self):
        queryset = super().get_queryset()

        status_filter = self.request.query_params.get("status")
        lorry_id = self.request.query_params.get("lorry")
        driver_id = self.request.query_params.get("driver")

        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())

        if lorry_id:
            queryset = queryset.filter(lorry_id=lorry_id)

        if driver_id:
            queryset = queryset.filter(driver_id=driver_id)

        return queryset

    @transaction.atomic
    def perform_create(self, serializer):
        lorry_id = serializer.validated_data["lorry"].id
        driver_id = serializer.validated_data["driver"].id

        # Always lock resources in the same order.
        lorry = get_object_or_404(
            Lorry.objects.select_for_update(),
            pk=lorry_id
        )

        driver = get_object_or_404(
            Driver.objects.select_for_update(),
            pk=driver_id
        )

        if lorry.status != Lorry.Status.AVAILABLE:
            raise ValidationError("This lorry is not available.")

        if not driver.is_active:
            raise ValidationError("This driver is inactive.")

        if Trip.objects.filter(
            lorry=lorry,
            status__in=ACTIVE_TRIP_STATUSES
        ).exists():
            raise ValidationError(
                "This lorry already has an active trip."
            )

        if Trip.objects.filter(
            driver=driver,
            status__in=ACTIVE_TRIP_STATUSES
        ).exists():
            raise ValidationError(
                "This driver already has an active trip."
            )

        serializer.save(
            assigned_by=self.request.user,
            status=Trip.Status.ASSIGNED
        )


class TripDetailView(BaseTransportView, generics.RetrieveAPIView):
    serializer_class = TripSerializer
    queryset = Trip.objects.select_related(
        "lorry", "driver", "booking", "sale"
    )


class TripStartView(BaseTransportView, APIView):

    @transaction.atomic
    def post(self, request, pk):
        # Lock resources in consistent order: lorry, driver, trip.
        trip_reference = get_object_or_404(Trip, pk=pk)

        lorry = get_object_or_404(
            Lorry.objects.select_for_update(),
            pk=trip_reference.lorry_id
        )

        driver = get_object_or_404(
            Driver.objects.select_for_update(),
            pk=trip_reference.driver_id
        )

        trip = get_object_or_404(
            Trip.objects.select_for_update(),
            pk=pk
        )

        if trip.status != Trip.Status.ASSIGNED:
            raise ValidationError(
                "Only assigned trips can be started."
            )

        if lorry.status != Lorry.Status.AVAILABLE:
            raise ValidationError(
                "The assigned lorry is not available."
            )

        if not driver.is_active:
            raise ValidationError(
                "The assigned driver is inactive."
            )

        trip.status = Trip.Status.IN_PROGRESS
        trip.started_at = timezone.now()
        trip.save(update_fields=[
            "status", "started_at", "updated_at"
        ])

        lorry.status = Lorry.Status.ON_TRIP
        lorry.save(update_fields=[
            "status", "updated_at"
        ])

        return Response(
            TripSerializer(trip).data,
            status=status.HTTP_200_OK
        )


class TripCompleteView(BaseTransportView, APIView):

    @transaction.atomic
    def post(self, request, pk):
        trip_reference = get_object_or_404(Trip, pk=pk)

        lorry = get_object_or_404(
            Lorry.objects.select_for_update(),
            pk=trip_reference.lorry_id
        )

        trip = get_object_or_404(
            Trip.objects.select_for_update(),
            pk=pk
        )

        if trip.status != Trip.Status.IN_PROGRESS:
            raise ValidationError(
                "Only trips in progress can be completed."
            )

        trip.status = Trip.Status.COMPLETED
        trip.completed_at = timezone.now()
        trip.save(update_fields=[
            "status", "completed_at", "updated_at"
        ])

        lorry.status = Lorry.Status.AVAILABLE
        lorry.save(update_fields=[
            "status", "updated_at"
        ])

        return Response(
            TripSerializer(trip).data,
            status=status.HTTP_200_OK
        )


class TripCancelView(BaseTransportView, APIView):

    @transaction.atomic
    def post(self, request, pk):
        trip = get_object_or_404(
            Trip.objects.select_for_update(),
            pk=pk
        )

        if trip.status not in [
            Trip.Status.PENDING,
            Trip.Status.ASSIGNED,
        ]:
            raise ValidationError(
                "Only pending or assigned trips can be cancelled."
            )

        trip.status = Trip.Status.CANCELLED
        trip.save(update_fields=[
            "status", "updated_at"
        ])

        return Response(
            TripSerializer(trip).data,
            status=status.HTTP_200_OK
        )


# -------------------------
# TRIP EXPENSES
# -------------------------

class TripExpenseListCreateView(
    BaseTransportView,
    generics.ListCreateAPIView
):
    serializer_class = TripExpenseSerializer

    queryset = TripExpense.objects.select_related(
        "trip", "recorded_by"
    ).order_by("-expense_date", "-created_at")

    def get_queryset(self):
        queryset = super().get_queryset()

        trip_id = self.request.query_params.get("trip")
        expense_type = self.request.query_params.get("expense_type")

        if trip_id:
            queryset = queryset.filter(trip_id=trip_id)

        if expense_type:
            queryset = queryset.filter(
                expense_type=expense_type.upper()
            )

        return queryset

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)


# -------------------------
# LORRY EXPENSES
# -------------------------

class LorryExpenseListCreateView(
    BaseTransportView,
    generics.ListCreateAPIView
):
    serializer_class = LorryExpenseSerializer

    queryset = LorryExpense.objects.select_related(
        "lorry", "recorded_by"
    ).order_by("-expense_date", "-created_at")

    def get_queryset(self):
        queryset = super().get_queryset()

        lorry_id = self.request.query_params.get("lorry")
        expense_type = self.request.query_params.get("expense_type")

        if lorry_id:
            queryset = queryset.filter(lorry_id=lorry_id)

        if expense_type:
            queryset = queryset.filter(
                expense_type=expense_type.upper()
            )

        return queryset

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)

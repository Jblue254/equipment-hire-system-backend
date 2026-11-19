
from rest_framework import serializers

from .models import Lorry, Driver, Trip, TripExpense, LorryExpense


ACTIVE_TRIP_STATUSES = [
    Trip.Status.PENDING,
    Trip.Status.ASSIGNED,
    Trip.Status.IN_PROGRESS,
]


class LorrySerializer(serializers.ModelSerializer):

    class Meta:
        model = Lorry
        fields = "__all__"
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )

    def validate_registration_number(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        if self.instance and "status" in attrs:
            if attrs["status"] != self.instance.status:
                has_active_trip = Trip.objects.filter(
                    lorry=self.instance,
                    status__in=ACTIVE_TRIP_STATUSES
                ).exists()

                if has_active_trip:
                    raise serializers.ValidationError({
                        "status": "Cannot change lorry status while it has an active trip."
                    })

        return attrs


class DriverSerializer(serializers.ModelSerializer):

    class Meta:
        model = Driver
        fields = "__all__"
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )

    def validate_phone_number(self, value):
        return value.strip()

    def validate_licence_number(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        if self.instance and attrs.get("is_active") is False:
            has_active_trip = Trip.objects.filter(
                driver=self.instance,
                status__in=ACTIVE_TRIP_STATUSES
            ).exists()

            if has_active_trip:
                raise serializers.ValidationError({
                    "is_active": "Cannot deactivate a driver who has an active trip."
                })

        return attrs


class TripSerializer(serializers.ModelSerializer):

    lorry_registration = serializers.CharField(
        source="lorry.registration_number",
        read_only=True
    )

    driver_name = serializers.CharField(
        source="driver.full_name",
        read_only=True
    )

    booking_number = serializers.CharField(
        source="booking.booking_number",
        read_only=True
    )

    sale_number = serializers.CharField(
        source="sale.sale_number",
        read_only=True
    )

    class Meta:
        model = Trip
        fields = "__all__"
        read_only_fields = (
            "id",
            "status",
            "started_at",
            "completed_at",
            "assigned_by",
            "created_at",
            "updated_at",
        )

    
    def validate(self, attrs):
        is_new = self.instance is None

        lorry = attrs.get(
            "lorry",
            getattr(self.instance, "lorry", None)
        )

        driver = attrs.get(
            "driver",
            getattr(self.instance, "driver", None)
        )

        booking = attrs.get(
            "booking",
            getattr(self.instance, "booking", None)
        )

        sale = attrs.get(
            "sale",
            getattr(self.instance, "sale", None)
        )

        lorry_changed = is_new or lorry != self.instance.lorry
        driver_changed = is_new or driver != self.instance.driver

        if bool(booking) == bool(sale):
            raise serializers.ValidationError(
                "A trip must belong to either a booking or a sale."
            )

        if lorry_changed and lorry.status != Lorry.Status.AVAILABLE:
            raise serializers.ValidationError({
                "lorry": "This lorry is not available."
            })

        if driver_changed and not driver.is_active:
            raise serializers.ValidationError({
                "driver": "This driver is inactive."
            })

        if booking and not booking.transport_required:
            raise serializers.ValidationError({
                "booking": "Transport is not required for this booking."
            })

        if sale and not sale.transport_required:
            raise serializers.ValidationError({
                "sale": "Transport is not required for this sale."
            })

        queryset = Trip.objects.filter(
            status__in=ACTIVE_TRIP_STATUSES
        )

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if lorry and queryset.filter(lorry=lorry).exists():
            raise serializers.ValidationError({
                "lorry": "This lorry already has an active trip."
            })

        if driver and queryset.filter(driver=driver).exists():
            raise serializers.ValidationError({
                "driver": "This driver already has an active trip."
            })

        return attrs



class TripExpenseSerializer(serializers.ModelSerializer):

    trip_reference = serializers.CharField(
        source="trip.id",
        read_only=True
    )

    class Meta:
        model = TripExpense
        fields = "__all__"
        read_only_fields = (
            "id",
            "recorded_by",
            "created_at",
        )

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Expense amount must be greater than zero."
            )
        return value

    def validate_trip(self, value):
        if value.status == Trip.Status.CANCELLED:
            raise serializers.ValidationError(
                "Cannot record expenses against a cancelled trip."
            )
        return value


class LorryExpenseSerializer(serializers.ModelSerializer):

    lorry_registration = serializers.CharField(
        source="lorry.registration_number",
        read_only=True
    )

    class Meta:
        model = LorryExpense
        fields = "__all__"
        read_only_fields = (
            "id",
            "recorded_by",
            "created_at",
        )

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Expense amount must be greater than zero."
            )
        return value

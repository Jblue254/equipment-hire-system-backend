
from decimal import Decimal

from django.db.models import Sum, F
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsAdminOrStorekeeper
from inventory.models import Equipment, Material
from bookings.models import Booking
from sales.models import Sale
from finance.models import Payment
from transport.models import Lorry, Trip


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrStorekeeper]

    def get(self, request):
        # EQUIPMENT STATISTICS
        equipment = {
            "total": Equipment.objects.filter(is_active=True).count(),
            "available": Equipment.objects.filter(
                is_active=True, status="AVAILABLE"
            ).count(),
            "reserved": Equipment.objects.filter(
                is_active=True, status="RESERVED"
            ).count(),
            "hired_out": Equipment.objects.filter(
                is_active=True, status="HIRED_OUT"
            ).count(),
            "under_maintenance": Equipment.objects.filter(
                is_active=True, status="UNDER_MAINTENANCE"
            ).count(),
            "damaged": Equipment.objects.filter(
                is_active=True, status="DAMAGED"
            ).count(),
        }

        # BOOKING STATISTICS
        bookings = {
            "total": Booking.objects.count(),
            "pending": Booking.objects.filter(status="PENDING").count(),
            "active": Booking.objects.filter(status="ACTIVE").count(),
            "overdue": Booking.objects.filter(status="OVERDUE").count(),
            "completed": Booking.objects.filter(status="COMPLETED").count(),
            "cancelled": Booking.objects.filter(status="CANCELLED").count(),
        }

        # MATERIAL STATISTICS
        active_materials = Material.objects.filter(is_active=True)

        low_stock_materials = active_materials.filter(
            stock_quantity__lte=0
        )

        materials = {
            "total": active_materials.count(),
            "low_stock": active_materials.filter(
                stock_quantity__lte=F("reorder_level")
            ).count(),
            "out_of_stock": low_stock_materials.count(),
        }

        # SALES STATISTICS
        sales = {
            "total": Sale.objects.count(),
            "pending": Sale.objects.filter(status="PENDING").count(),
            "confirmed": Sale.objects.filter(status="CONFIRMED").count(),
            "dispatched": Sale.objects.filter(status="DISPATCHED").count(),
            "completed": Sale.objects.filter(status="COMPLETED").count(),
            "cancelled": Sale.objects.filter(status="CANCELLED").count(),
        }

        sales_revenue = Sale.objects.filter(
            status__in=["DISPATCHED", "COMPLETED"]
        ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")

        # PAYMENT STATISTICS
        confirmed_payments = Payment.objects.filter(status="CONFIRMED")

        payments_received = confirmed_payments.aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        finance = {
            "payments_received": payments_received,
            "pending_payments": Payment.objects.filter(status="PENDING").count(),
            "confirmed_payments": confirmed_payments.count(),
            "sales_revenue": sales_revenue,
        }

        # TRANSPORT STATISTICS
        transport = {
            "total_lorries": Lorry.objects.count(),
            "available_lorries": Lorry.objects.filter(
                status="AVAILABLE"
            ).count(),
            "active_trips": Trip.objects.filter(
                status="IN_PROGRESS"
            ).count(),
            "pending_trips": Trip.objects.filter(
                status="PENDING"
            ).count(),
        }

        return Response({
            "equipment": equipment,
            "bookings": bookings,
            "materials": materials,
            "sales": sales,
            "finance": finance,
            "transport": transport,
        })

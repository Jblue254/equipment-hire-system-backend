from django.urls import path

from .views import (
    MpesaSTKPushView,
    PaymentListCreateView,
    PaymentVerificationView,
    BookingPaymentBalanceView,
    SalePaymentBalanceView,
)


urlpatterns = [
    path(
        "payments/",
        PaymentListCreateView.as_view(),
        name="payment-list-create"
    ),

    path(
        "payments/<int:pk>/verify/",
        PaymentVerificationView.as_view(),
        name="payment-verify"
    ),
    path(
    "bookings/<int:booking_id>/balance/",
    BookingPaymentBalanceView.as_view(),
    name="booking-payment-balance"
    ),
    path(
    "sales/<int:sale_id>/balance/",
    SalePaymentBalanceView.as_view(),
    name="sale-payment-balance"
),
path(
    "mpesa/stk-push/",
    MpesaSTKPushView.as_view(),
    name="mpesa-stk-push"
),
]
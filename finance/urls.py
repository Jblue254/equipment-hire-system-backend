from django.urls import path

from .views import (
    PaymentListCreateView,
    PaymentVerificationView,
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
]
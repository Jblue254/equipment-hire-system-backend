
from django.urls import path

from .views import (
    BookingListCreateView,
    BookingDetailView,
    CreditApprovalListView,
    CreditApprovalDecisionView,
)


urlpatterns = [
    path(
        "",
        BookingListCreateView.as_view(),
        name="booking-list-create"
    ),

    path(
        "<int:pk>/",
        BookingDetailView.as_view(),
        name="booking-detail"
    ),

    path(
        "credit-approvals/",
        CreditApprovalListView.as_view(),
        name="credit-approval-list"
    ),

    path(
        "credit-approvals/<int:pk>/decision/",
        CreditApprovalDecisionView.as_view(),
        name="credit-approval-decision"
    ),
]

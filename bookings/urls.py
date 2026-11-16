
from django.urls import path

from .views import (
    BookingListCreateView,
    BookingDetailView,
    BookingDecisionView,
    BookingDispatchView,
    BookingReturnListCreateView,
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

    path(
        "<int:pk>/decision/",
        BookingDecisionView.as_view(),
        name="booking-decision"
    ),

    path(
        "<int:pk>/dispatch/",
        BookingDispatchView.as_view(),
        name="booking-dispatch"
    ),

    path(
        "returns/",
        BookingReturnListCreateView.as_view(),
        name="booking-returns"
    ),
]

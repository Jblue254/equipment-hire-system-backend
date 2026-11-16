
from django.urls import path

from .views import (
    SaleListCreateView,
    SaleDetailView,
    SaleConfirmationView,
    SaleCancellationView,
    SaleDispatchView,
    SaleCompletionView,
)

urlpatterns = [
    path("", SaleListCreateView.as_view(), name="sale-list-create"),
    path("<int:pk>/", SaleDetailView.as_view(), name="sale-detail"),
    path(
        "<int:pk>/confirm/",
        SaleConfirmationView.as_view(),
        name="sale-confirm"
    ),
    path(
        "<int:pk>/cancel/",
        SaleCancellationView.as_view(),
        name="sale-cancel"
    ),
    path(
        "<int:pk>/dispatch/",
        SaleDispatchView.as_view(),
        name="sale-dispatch"
    ),
    path(
        "<int:pk>/complete/",
        SaleCompletionView.as_view(),
        name="sale-complete"
    ),
]

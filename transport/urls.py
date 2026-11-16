
from django.urls import path

from .views import (
    LorryListCreateView,
    LorryDetailView,
    DriverListCreateView,
    DriverDetailView,
    TripListCreateView,
    TripDetailView,
    TripStartView,
    TripCompleteView,
    TripCancelView,
    TripExpenseListCreateView,
    LorryExpenseListCreateView,
)

urlpatterns = [
    # Lorries
    path("lorries/", LorryListCreateView.as_view(), name="lorry-list-create"),
    path("lorries/<int:pk>/", LorryDetailView.as_view(), name="lorry-detail"),

    # Drivers
    path("drivers/", DriverListCreateView.as_view(), name="driver-list-create"),
    path("drivers/<int:pk>/", DriverDetailView.as_view(), name="driver-detail"),

    # Trips
    path("trips/", TripListCreateView.as_view(), name="trip-list-create"),
    path("trips/<int:pk>/", TripDetailView.as_view(), name="trip-detail"),
    path("trips/<int:pk>/start/", TripStartView.as_view(), name="trip-start"),
    path("trips/<int:pk>/complete/", TripCompleteView.as_view(), name="trip-complete"),
    path("trips/<int:pk>/cancel/", TripCancelView.as_view(), name="trip-cancel"),

    # Trip expenses
    path("trip-expenses/", TripExpenseListCreateView.as_view(), name="trip-expense-list-create"),

    # Lorry expenses
    path("lorry-expenses/", LorryExpenseListCreateView.as_view(), name="lorry-expense-list-create"),
]


from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/inventory/", include("inventory.urls")),
    path("api/bookings/", include("bookings.urls")),
    path("api/finance/", include("finance.urls")),
    path("api/sales/", include("sales.urls")),
    path("api/transport/", include("transport.urls")),
    path("api/notifications/", include("notifications.urls")),
   
]
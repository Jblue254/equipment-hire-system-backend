
from django.contrib import admin

from .models import (
    Booking,
    BookingItem,
    CreditApproval,
    BookingReturn,
    ReturnItem,
)


admin.site.register(Booking)
admin.site.register(BookingItem)
admin.site.register(CreditApproval)
admin.site.register(BookingReturn)
admin.site.register(ReturnItem)

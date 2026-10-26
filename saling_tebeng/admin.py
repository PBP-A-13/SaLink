from django.contrib import admin
from .models import Vehicle, RideOffer, RideBooking, RideRequest, RideSchedule

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('owner', 'vehicle_type', 'brand', 'model', 'license_plate', 'capacity', 'is_active')

@admin.register(RideOffer)
class RideOfferAdmin(admin.ModelAdmin):
    list_display = ('driver', 'vehicle', 'is_active', 'created_at')

@admin.register(RideSchedule)
class RideScheduleAdmin(admin.ModelAdmin):
    list_display = ('ride_offer', 'date', 'departure_time', 'origin', 'destination', 'available_seats', 'price', 'is_active')

@admin.register(RideBooking)
class RideBookingAdmin(admin.ModelAdmin):
    list_display = ('ride_schedule', 'passenger', 'seats', 'status', 'booked_at')

@admin.register(RideRequest)
class RideRequestAdmin(admin.ModelAdmin):
    list_display = ('passenger', 'date', 'requested_time', 'origin', 'destination', 'status')

from django.contrib import admin
from .models import (
    RideBooking,
    RideChatMessage,
    RideConversation,
    RideOffer,
    RideRequest,
    RideSchedule,
    Vehicle,
)

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('owner', 'vehicle_type', 'brand', 'model', 'license_plate', 'capacity', 'is_active')

@admin.register(RideOffer)
class RideOfferAdmin(admin.ModelAdmin):
    list_display = ('driver', 'vehicle', 'is_active', 'created_at')

@admin.register(RideSchedule)
class RideScheduleAdmin(admin.ModelAdmin):
    list_display = ('ride_offer', 'date', 'departure_time', 'origin', 'destination', 'total_seats', 'price', 'is_active')

@admin.register(RideBooking)
class RideBookingAdmin(admin.ModelAdmin):
    list_display = ('ride_schedule', 'ride_date', 'passenger', 'seats', 'status', 'booked_at')

@admin.register(RideConversation)
class RideConversationAdmin(admin.ModelAdmin):
    list_display = ('ride_schedule', 'passenger', 'updated_at')

@admin.register(RideChatMessage)
class RideChatMessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender', 'created_at', 'is_read')

@admin.register(RideRequest)
class RideRequestAdmin(admin.ModelAdmin):
    list_display = ('passenger', 'date', 'requested_time', 'origin', 'destination', 'status')

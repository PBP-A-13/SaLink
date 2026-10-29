from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class Vehicle(models.Model):
    VEHICLE_TYPE_CHOICES = [
        ('motor', 'Motor'),
        ('mobil', 'Mobil'),
    ]

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='vehicles'
    )
    vehicle_type = models.CharField(
        max_length=10,
        choices=VEHICLE_TYPE_CHOICES
    )
    brand = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    license_plate = models.CharField(max_length=20)
    capacity = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.brand} {self.model} - {self.license_plate}"


class RideOffer(models.Model):
    driver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ride_offers'
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='ride_offers'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Tawaran dari {self.driver.username}"


class RideSchedule(models.Model):
    ride_offer = models.ForeignKey(
        RideOffer,
        on_delete=models.CASCADE,
        related_name='schedules'
    )

    date = models.DateField()
    departure_time = models.TimeField()

    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)

    origin_latitude = models.FloatField(null=True, blank=True)
    origin_longitude = models.FloatField(null=True, blank=True)

    destination_latitude = models.FloatField(null=True, blank=True)
    destination_longitude = models.FloatField(null=True, blank=True)

    available_seats = models.PositiveIntegerField(default=1)

    price = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    def clean(self):
        vehicle_type = self.ride_offer.vehicle.vehicle_type

        if vehicle_type == 'motor':
            if self.price not in [0, 5000]:
                raise ValidationError(
                    'Harga motor hanya boleh gratis atau Rp5.000.'
                )

        elif vehicle_type == 'mobil':
            if self.price not in [0, 7000]:
                raise ValidationError(
                    'Harga mobil hanya boleh gratis atau Rp7.000.'
                )

    def __str__(self):
        return (
            f"{self.ride_offer.driver.username} - "
            f"{self.date} {self.departure_time}"
        )


class RideRequest(models.Model):
    STATUS_CHOICES = [
        ('searching', 'Searching'),
        ('matched', 'Matched'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    passenger = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ride_requests'
    )

    date = models.DateField()
    requested_time = models.TimeField()

    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)

    origin_latitude = models.FloatField(null=True, blank=True)
    origin_longitude = models.FloatField(null=True, blank=True)

    destination_latitude = models.FloatField(null=True, blank=True)
    destination_longitude = models.FloatField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='searching'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.passenger.username} - "
            f"{self.origin} ke {self.destination}"
        )


class RideBooking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    ride_schedule = models.ForeignKey(
        RideSchedule,
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    passenger = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ride_bookings'
    )

    seats = models.PositiveIntegerField(default=1)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    booked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.passenger.username} - "
            f"{self.ride_schedule}"
        )
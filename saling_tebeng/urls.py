from django.urls import path
from . import views

app_name = 'saling_tebeng'

urlpatterns = [
    path('', views.nebeng_list, name='index'),
    path('nebeng/', views.nebeng_list, name='nebeng_list'),
    path('nebeng/tawarkan/', views.tawarkan_tebengan, name='tawarkan_tebengan'),
    path('nebeng/jadwal/<int:schedule_id>/batal/', views.cancel_schedule, name='cancel_schedule'),
    path('nebeng/jadwal/<int:schedule_id>/gabung/', views.join_ride, name='join_ride'),
    path('nebeng/jadwal/<int:schedule_id>/chat/', views.ride_chat, name='ride_chat'),
    path('nebeng/jadwal/<int:schedule_id>/chat/gabung/', views.join_from_chat, name='join_from_chat'),
    path('nebeng/saya/', views.my_bookings, name='my_bookings'),
    path('nebeng/booking/<int:booking_id>/batal/', views.cancel_booking, name='cancel_booking'),
]
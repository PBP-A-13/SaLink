
from django.urls import path
from . import views
from user_page.views import module_login


app_name = 'saling_bagi'

urlpatterns = [
    path('login/', module_login, name='login'),

    path('', views.index, name='index'),

    path('tambah/', views.tambah_makanan, name='tambah_makanan'),

    path('ajukan/<int:id>/', views.ajukan_janji, name='ajukan_janji'),

    path('janji-temu/', views.janji_temu, name='janji_temu'),

    path(
        'janji-temu/<int:id>/keputusan/',
        views.keputusan_janji,
        name='keputusan_janji'
    ),

    path(
        'janji-temu/<int:id>/selesai/',
        views.selesaikan_janji,
        name='selesaikan_janji'
    ),
]

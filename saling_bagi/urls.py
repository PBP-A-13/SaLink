from django.urls import path
from . import views

app_name = 'saling_bagi'

urlpatterns = [
    path('', views.index, name='index'),
    # Tambahkan rute ini untuk halaman form
    path('tambah/', views.tambah_makanan, name='tambah_makanan'),
    path('<int:id>/ambil/', views.ambil_makanan, name='ambil_makanan'),
]
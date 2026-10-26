from django.urls import path
from . import views

app_name = 'saling_bagi'

urlpatterns = [
    path('', views.index, name='index'),
    path('<int:id>/ambil/', views.ambil_makanan, name='ambil_makanan'),
]
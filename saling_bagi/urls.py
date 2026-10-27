from django.urls import path
from . import views
from user_page.views import module_login

app_name = 'saling_bagi'

urlpatterns = [
    path('login/', module_login, name='login'),
    path('', views.index, name='index'),
    path('<int:id>/ambil/', views.ambil_makanan, name='ambil_makanan'),
]
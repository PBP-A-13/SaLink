from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.show_main, name='show_main'),
    path('panduan-cod/', views.panduan_cod, name='panduan_cod'),
    path('faq/', views.faq, name='faq'),
]

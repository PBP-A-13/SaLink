from django.urls import path
from .views import show_saling_bagi

app_name = 'saling_bagi'

urlpatterns = [
    path('', show_saling_bagi, name='show_saling_bagi'),
]
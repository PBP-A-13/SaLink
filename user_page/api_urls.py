from django.urls import path
from . import api_views

app_name = 'user_page_api'

urlpatterns = [
    path('register/', api_views.register_api, name='register'),
    path('login/', api_views.login_api, name='login'),
    path('logout/', api_views.logout_api, name='logout'),
    path('profile/', api_views.profile_api, name='profile'),
]

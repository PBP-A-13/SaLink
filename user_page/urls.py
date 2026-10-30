from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = 'user_page'

urlpatterns = [
    path('login/', views.SaLinkLoginView.as_view(), name='login'),
    path('register/', views.register, name='register'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('profile/', views.profile, name='profile'),
    path('delete-account/', views.delete_account, name='delete_account'),
    path('sso/login/', views.sso_login, name='sso_login'),
    path('sso/link/', views.sso_link, name='sso_link'),
    path('sso/callback/', views.sso_callback, name='sso_callback'),
]

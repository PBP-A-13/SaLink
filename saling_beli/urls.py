from django.urls import path

from . import views

app_name = 'saling_beli'

urlpatterns = [
    path('', views.listings, name='listing-list'),
    path('create/', views.listing_create, name='listing-create'),
    path('<uuid:listing_id>/', views.listing_detail, name='listing-detail'),
    path('<uuid:listing_id>/update/', views.listing_update, name='listing-update'),
    path('<uuid:listing_id>/delete/', views.listing_delete, name='listing-delete'),
]
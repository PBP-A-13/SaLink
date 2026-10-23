from django.urls import path

from . import views

app_name = 'saling_beli'

urlpatterns = [
    # Halaman HTML & Detail
    path('', views.index, name='index'),
    path('detail/<uuid:listing_id>/', views.item_detail, name='item_detail'),

    # JSON / REST API Endpoints
    path('json/', views.listings, name='listing-list'),
    path('json/all/', views.listings_json, name='listing-json'),
    path('create/', views.listing_create, name='listing-create'),
    path('<uuid:listing_id>/', views.listing_detail, name='listing-detail'),
    path('<uuid:listing_id>/update/', views.listing_update, name='listing-update'),
    path('<uuid:listing_id>/delete/', views.listing_delete, name='listing-delete'),
]
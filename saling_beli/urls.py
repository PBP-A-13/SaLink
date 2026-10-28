from django.urls import path
from user_page.views import module_login
from . import views

app_name = 'saling_beli'

urlpatterns = [
    # Alias login modul bersama (redirect ke login user_page)
    path('login/', module_login, name='login'),

    # Halaman HTML Web (Katalog, Form Tambah Barang, dan Detail)
    path('', views.index, name='index'),
    path('tambah/', views.item_create_page, name='item_create'),
    path('detail/<uuid:listing_id>/', views.item_detail, name='item_detail'),

    # Endpoint Fitur Nego Harga & Transaksi COD
    path('detail/<uuid:listing_id>/offer/', views.make_offer, name='make-offer'),
    path('offer/<uuid:offer_id>/respond/', views.respond_offer, name='respond-offer'),
    path('detail/<uuid:listing_id>/order/', views.create_order, name='create-order'),
    path('order/<uuid:order_id>/update-stage/', views.update_order_stage, name='update-order-stage'),

    # REST / JSON API untuk integrasi mobile atau AJAX
    path('json/', views.listings, name='listing-list'),
    path('json/all/', views.listings_json, name='listing-json'),
    path('create/', views.listing_create, name='listing-create'),
    path('<uuid:listing_id>/', views.listing_detail, name='listing-detail'),
    path('<uuid:listing_id>/update/', views.listing_update, name='listing-update'),
    path('<uuid:listing_id>/delete/', views.listing_delete, name='listing-delete'),
    path('<uuid:listing_id>/upload-image/', views.upload_item_image, name='upload-image'),

    # Endpoint Percakapan Chat & Notifikasi Realtime
    path('detail/<uuid:listing_id>/chats/', views.item_chats, name='item-chats'),
    path('api/notifications/', views.user_notifications, name='user-notifications'),
    path('api/notifications/stream/', views.notification_stream, name='notification-stream'),
    path('api/notifications/mark-read/', views.mark_notifications_read, name='mark-notifications-read'),
]

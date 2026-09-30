from django.urls import path
from . import views

app_name = 'saling_pinjam'

urlpatterns = [
    path('', views.item_list, name='item_list'),
    path('create/', views.item_create, name='item_create'),
    path('my-borrows/', views.my_borrows, name='my_borrows'),
    path('<uuid:id>/', views.item_detail, name='item_detail'),
    path('<uuid:id>/request/', views.request_borrow, name='request_borrow'),
    path('request/<uuid:request_id>/status/<str:new_status>/', views.update_request_status, name='update_status'),
]

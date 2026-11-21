from django.urls import path
from . import api, views
from user_page.views import module_login

app_name = 'saling_pinjam'

urlpatterns = [
    # Halaman HTML Web
    path('login/', module_login, name='login'),
    path('', views.item_list, name='item_list'),
    path('create/', views.item_create, name='item_create'),
    path('my-borrows/', views.my_borrows, name='my_borrows'),
    path('<uuid:id>/', views.item_detail, name='item_detail'),
    path('<uuid:id>/edit/', views.item_edit, name='item_edit'),
    path('<uuid:id>/delete/', views.item_delete, name='item_delete'),
    path('<uuid:id>/request/', views.request_borrow, name='request_borrow'),
    path('request/<uuid:request_id>/cancel/', views.cancel_request, name='cancel_request'),
    path('request/<uuid:request_id>/<str:new_status>/', views.update_request_status, name='update_request_status'),

    # REST / JSON API (Mobile & Web Client)
    path('api/items/', api.ItemListCreateView.as_view(), name='api_items'),
    path('api/items/<uuid:id>/', api.ItemDetailView.as_view(), name='api_item_detail'),
    path('api/items/<uuid:id>/update/', api.ItemUpdateView.as_view(), name='api_item_update'),
    path('api/items/<uuid:id>/delete/', api.ItemDeleteView.as_view(), name='api_item_delete'),
    path('api/items/<uuid:id>/request/', api.BorrowCreateView.as_view(), name='api_request_borrow'),
    path('api/my-borrows/', api.MyBorrowsView.as_view(), name='api_my_borrows'),
    path('api/requests/<uuid:request_id>/cancel/', api.CancelRequestView.as_view(), name='api_cancel_request'),
    path('api/requests/<uuid:request_id>/status/', api.UpdateRequestStatusView.as_view(), name='api_update_status'),
    path('api/requests/<uuid:request_id>/confirm-handover/', api.ConfirmHandoverView.as_view(), name='api_confirm_handover'),
    path('api/requests/<uuid:request_id>/confirm-return/', api.ConfirmReturnView.as_view(), name='api_confirm_return'),
]

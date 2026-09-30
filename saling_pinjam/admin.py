from django.contrib import admin
from .models import BorrowItem, BorrowRequest

@admin.register(BorrowItem)
class BorrowItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'category', 'condition', 'max_duration_days', 'deposit_fee', 'status', 'created_at')
    list_filter = ('category', 'condition', 'status')
    search_fields = ('name', 'description', 'pickup_location', 'owner__username')

@admin.register(BorrowRequest)
class BorrowRequestAdmin(admin.ModelAdmin):
    list_display = ('item', 'borrower', 'start_date', 'end_date', 'status', 'created_at')
    list_filter = ('status', 'start_date', 'end_date')
    search_fields = ('item__name', 'borrower__username', 'notes')

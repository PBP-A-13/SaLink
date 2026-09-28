from django.contrib import admin
from .models import ItemListing

@admin.register(ItemListing)
class ItemListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'category', 'condition', 'price', 'is_free', 'status', 'created_at')
    list_filter = ('category', 'condition', 'is_free', 'status')
    search_fields = ('title', 'description', 'pickup_location', 'user__username')

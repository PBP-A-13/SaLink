from django.contrib import admin
from .models import ItemListing, PriceOffer, TransactionOrder, Conversation, ItemChatMessage, UserNotification


@admin.register(ItemListing)
class ItemListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'category', 'condition', 'price', 'is_free', 'status', 'created_at')
    list_filter = ('category', 'condition', 'is_free', 'status', 'created_at')
    search_fields = ('title', 'description', 'pickup_location', 'user__username', 'payout_account_number')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(PriceOffer)
class PriceOfferAdmin(admin.ModelAdmin):
    list_display = ('item', 'buyer', 'offered_price', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('item__title', 'buyer__username', 'note')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(TransactionOrder)
class TransactionOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'item', 'buyer', 'seller', 'agreed_price', 'stage', 'created_at')
    list_filter = ('stage', 'created_at')
    search_fields = ('id', 'item__title', 'buyer__username', 'seller__username', 'payment_proof_note')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('item', 'buyer', 'seller', 'updated_at')
    search_fields = ('item__title', 'buyer__username', 'seller__username')


@admin.register(ItemChatMessage)
class ItemChatMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'conversation', 'message', 'created_at')
    search_fields = ('sender__username', 'message')
    readonly_fields = ('id', 'created_at')


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('user__username', 'title', 'message')
    readonly_fields = ('id', 'created_at')

from django.db import migrations


def backfill_conversations(apps, schema_editor):
    Conversation = apps.get_model('saling_beli', 'Conversation')
    ItemChatMessage = apps.get_model('saling_beli', 'ItemChatMessage')

    for message in ItemChatMessage.objects.filter(conversation__isnull=True).select_related('item', 'sender', 'recipient'):
        seller = message.item.user
        buyer = message.sender if message.sender_id != seller.pk else message.recipient
        if buyer.pk == seller.pk:
            continue

        conversation, _ = Conversation.objects.get_or_create(
            item=message.item,
            buyer=buyer,
            defaults={'seller': seller},
        )
        message.conversation = conversation
        message.save(update_fields=['conversation'])


def reverse_backfill(apps, schema_editor):
    ItemChatMessage = apps.get_model('saling_beli', 'ItemChatMessage')
    ItemChatMessage.objects.update(conversation=None)


class Migration(migrations.Migration):

    dependencies = [
        ('saling_beli', '0006_conversation_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_conversations, reverse_backfill),
    ]

from django.db import migrations, models


def keep_one_active_order_per_item(apps, schema_editor):
    Order = apps.get_model('saling_beli', 'TransactionOrder')
    Item = apps.get_model('saling_beli', 'ItemListing')
    active_stages = ('MENUNGGU_TRANSFER', 'BUKTI_DIUNGGAH', 'DIKONFIRMASI', 'JANJI_TEMU_COD')
    item_ids = Order.objects.filter(stage__in=active_stages).values_list('item_id', flat=True).distinct()
    for item_id in item_ids.iterator():
        active_orders = Order.objects.filter(item_id=item_id, stage__in=active_stages).order_by('-updated_at', '-created_at', '-pk')
        keep_id = active_orders.values_list('pk', flat=True).first()
        active_orders.exclude(pk=keep_id).update(stage='BATAL')
        Item.objects.filter(pk=item_id).update(status='RESERVED')


class Migration(migrations.Migration):

    dependencies = [
        ('saling_beli', '0007_backfill_conversations'),
    ]

    operations = [
        migrations.AddField(
            model_name='transactionorder',
            name='buyer_confirmed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='transactionorder',
            name='seller_confirmed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(keep_one_active_order_per_item, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='transactionorder',
            constraint=models.UniqueConstraint(
                condition=~models.Q(('stage__in', ['BATAL', 'SELESAI'])),
                fields=('item',),
                name='uniq_active_order_per_item',
            ),
        ),
    ]

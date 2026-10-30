from django.db import migrations, models


def backfill_weekly_occurrences(apps, schema_editor):
    RideSchedule = apps.get_model('saling_tebeng', 'RideSchedule')
    RideBooking = apps.get_model('saling_tebeng', 'RideBooking')
    database = schema_editor.connection.alias

    for schedule in RideSchedule.objects.using(database).iterator():
        booked_seats = sum(
            RideBooking.objects.using(database)
            .filter(ride_schedule_id=schedule.pk)
            .exclude(status='cancelled')
            .values_list('seats', flat=True)
        )
        schedule.total_seats = schedule.available_seats + booked_seats
        schedule.save(update_fields=['total_seats'], using=database)
        RideBooking.objects.using(database).filter(
            ride_schedule_id=schedule.pk,
        ).update(ride_date=schedule.date)


class Migration(migrations.Migration):

    dependencies = [
        ('saling_tebeng', '0002_rideoffer_riderequest_rideschedule_ridebooking_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='rideschedule',
            name='total_seats',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='ridebooking',
            name='ride_date',
            field=models.DateField(null=True),
        ),
        migrations.RunPython(
            backfill_weekly_occurrences,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='ridebooking',
            name='ride_date',
            field=models.DateField(),
        ),
    ]

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('saling_tebeng', '0003_weekly_ride_occurrences'),
    ]

    operations = [
        migrations.CreateModel(
            name='RideConversation',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('passenger', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ride_conversations',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('ride_schedule', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='conversations',
                    to='saling_tebeng.rideschedule',
                )),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='RideChatMessage',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID',
                )),
                ('message', models.TextField(max_length=2000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_read', models.BooleanField(default=False)),
                ('conversation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='messages',
                    to='saling_tebeng.rideconversation',
                )),
                ('sender', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sent_ride_messages',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='rideconversation',
            constraint=models.UniqueConstraint(
                fields=('ride_schedule', 'passenger'),
                name='uniq_ride_conversation_schedule_passenger',
            ),
        ),
    ]

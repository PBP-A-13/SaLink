from django.db import migrations
from django.contrib.auth.hashers import make_password

def update_user_passwords(apps, schema_editor):
    User = apps.get_model('auth', 'User')

    accounts = {
        'balqis': 'haihaihaihaihaihaihaihaihai?',
        'cruel_ella': 'mlbb1234mlbb1234',
        'dino': 'dinodinowhereyouare',
        'sternum': 'mlbb1234mlbb1234',
        'sternum.clavicula': 'mlbb1234mlbb1234',
        'zetian': 'mlbb1234mlbb1234',
    }

    for username, raw_password in accounts.items():
        hashed = make_password(raw_password)
        try:
            user = User.objects.get(username=username)
            user.password = hashed
            user.save()
        except User.DoesNotExist:
            User.objects.create(
                username=username,
                email=f'{username}@ui.ac.id',
                password=hashed,
                is_active=True,
            )

class Migration(migrations.Migration):

    dependencies = [
        ('user_page', '0002_ssoidentity'),
    ]

    operations = [
        migrations.RunPython(update_user_passwords, migrations.RunPython.noop),
    ]

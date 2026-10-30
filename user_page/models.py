from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    def __str__(self):
        return f"Profile of {self.user.username}"

class SSOIdentity(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='sso_identity',
    )
    provider = models.CharField(max_length=30, default='ui')
    subject = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['provider', 'subject'],
                name='unique_sso_provider_subject',
            )
        ]

    def __str__(self):
        return f'{self.provider}: {self.subject} ({self.user.username})'

@receiver(post_save, sender=User)
def create_or_save_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()
        else:
            UserProfile.objects.create(user=instance)


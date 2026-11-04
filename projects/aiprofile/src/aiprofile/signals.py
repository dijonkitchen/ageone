from typing import Any

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender: Any, instance: Any, created: bool, **kwargs: Any) -> None:
    """A new user, which GitHub sign-in creates, gets an empty hidden profile."""
    if created:
        Profile.objects.get_or_create(user=instance)

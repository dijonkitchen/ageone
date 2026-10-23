from django.conf import settings
from django.db import models


class Visibility(models.TextChoices):
    HIDDEN = "hidden"
    SEARCHABLE = "searchable"
    PUBLIC = "public"


class Profile(models.Model):
    """A worker's profile. Starts hidden and empty; only accepted patches fill it."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    visibility = models.CharField(
        max_length=12, choices=Visibility.choices, default=Visibility.HIDDEN
    )


class Evidence(models.Model):
    """One verified fact from a public source, deduplicated by (source, key) per user."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    source = models.CharField(max_length=40)
    key = models.CharField(max_length=200)
    text = models.TextField()
    url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "source", "key"], name="evidence_once"
            )
        ]


class PatchStatus(models.TextChoices):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Patch(models.Model):
    """A set of proposed claims. Only an accepted patch changes the profile."""

    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="patches"
    )
    status = models.CharField(
        max_length=10, choices=PatchStatus.choices, default=PatchStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)


class Claim(models.Model):
    """One statement of a patch; always cites at least one evidence item."""

    patch = models.ForeignKey(Patch, on_delete=models.CASCADE, related_name="claims")
    text = models.CharField(max_length=300)
    evidence = models.ManyToManyField(Evidence, related_name="claims")


class JobStatus(models.TextChoices):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Job(models.Model):
    """A refresh request the background worker picks up."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=10, choices=JobStatus.choices, default=JobStatus.QUEUED
    )
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

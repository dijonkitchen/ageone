"""The database-backed job queue: a refresh pulls evidence, then proposes a patch."""

from collections.abc import Callable

from django.contrib.auth.base_user import AbstractBaseUser
from django.db import transaction

from . import github, synth
from .models import Claim, Evidence, Job, JobStatus, Patch, Profile

ChatFactory = Callable[[], synth.Chat]


def github_login(user: AbstractBaseUser) -> str:
    """The GitHub login of a signed-in user; allauth stores it as the username."""
    return user.get_username()


def run_job(
    job: Job,
    fetch: github.Fetch = github.fetch_json,
    chat: ChatFactory = synth.openrouter_chat,
) -> None:
    job.status = JobStatus.RUNNING
    job.save(update_fields=["status"])
    try:
        github.ingest(job.user, github_login(job.user), fetch)
        propose_patch(job.user.profile, chat())
        job.status = JobStatus.DONE
    except Exception as error:  # noqa: BLE001 - recorded on the job for the worker to see
        job.status, job.error = JobStatus.FAILED, str(error)
    job.save(update_fields=["status", "error"])


def propose_patch(profile: Profile, chat: synth.Chat) -> Patch | None:
    """Store a pending patch of claims that cite this user's evidence, or None if none survive.

    Evidence already cited by an earlier patch is not offered again.
    """
    cited = Claim.objects.filter(patch__profile=profile).values_list(
        "evidence", flat=True
    )
    fresh = Evidence.objects.filter(user=profile.user).exclude(id__in=cited)
    items = [synth.EvidenceItem(e.id, e.text) for e in fresh]
    claims = synth.synthesize(items, chat)
    if not claims:
        return None
    with transaction.atomic():
        patch = Patch.objects.create(profile=profile)
        for proposed in claims:
            claim = Claim.objects.create(patch=patch, text=proposed.text)
            claim.evidence.set(proposed.evidence)
    return patch


def next_job() -> Job | None:
    with transaction.atomic():
        job = (
            Job.objects.select_for_update()
            .filter(status=JobStatus.QUEUED)
            .order_by("id")
            .first()
        )
        if job:
            job.status = JobStatus.RUNNING
            job.save(update_fields=["status"])
        return job

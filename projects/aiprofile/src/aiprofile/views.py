from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Claim, Job, Patch, PatchStatus, Profile, Visibility


def signed_in(request: HttpRequest) -> User:
    """The user of a request that login_required has already vetted."""
    assert isinstance(request.user, User)
    return request.user


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    profile = signed_in(request).profile
    patches = profile.patches.prefetch_related("claims__evidence").order_by("-id")
    return render(
        request,
        "aiprofile/dashboard.html",
        {
            "profile": profile,
            "pending": patches.filter(status=PatchStatus.PENDING),
            "accepted_claims": accepted_claims(profile),
            "jobs": Job.objects.filter(user=signed_in(request)).order_by("-id")[:5],
            "visibilities": Visibility.choices,
        },
    )


def accepted_claims(profile: Profile) -> list[Claim]:
    return list(
        Claim.objects.filter(patch__profile=profile, patch__status=PatchStatus.ACCEPTED)
        .prefetch_related("evidence")
        .order_by("id")
    )


@login_required
@require_POST
def refresh(request: HttpRequest) -> HttpResponse:
    Job.objects.create(user=signed_in(request))
    return redirect("dashboard")


@login_required
@require_POST
def set_visibility(request: HttpRequest) -> HttpResponse:
    value = request.POST.get("visibility", "")
    if value in Visibility.values:
        profile = signed_in(request).profile
        profile.visibility = value
        profile.save(update_fields=["visibility"])
    return redirect("dashboard")


@login_required
@require_POST
def decide(request: HttpRequest, patch_id: int, decision: str) -> HttpResponse:
    """Accept or reject a pending patch of the signed-in worker's own profile."""
    if decision not in ("accept", "reject"):
        raise Http404
    patch = get_object_or_404(
        Patch, id=patch_id, profile__user=signed_in(request), status=PatchStatus.PENDING
    )
    patch.status = (
        PatchStatus.ACCEPTED if decision == "accept" else PatchStatus.REJECTED
    )
    patch.save(update_fields=["status"])
    return redirect("dashboard")


def public_profile(request: HttpRequest, slug: str) -> HttpResponse:
    profile = get_object_or_404(
        Profile, user__username=slug, visibility=Visibility.PUBLIC
    )
    return render(
        request,
        "aiprofile/public.html",
        {"profile": profile, "claims": accepted_claims(profile)},
    )

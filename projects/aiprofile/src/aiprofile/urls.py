from django.urls import include, path

from . import views

urlpatterns = [
    path("accounts/", include("allauth.urls")),
    path("", views.dashboard, name="dashboard"),
    path("refresh/", views.refresh, name="refresh"),
    path("visibility/", views.set_visibility, name="visibility"),
    path("patches/<int:patch_id>/<str:decision>/", views.decide, name="decide"),
    path("u/<str:slug>/", views.public_profile, name="public_profile"),
]

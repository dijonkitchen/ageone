from django.apps import AppConfig


class AiprofileConfig(AppConfig):
    name = "aiprofile"

    def ready(self) -> None:
        from . import signals  # noqa: F401

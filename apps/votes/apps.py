from django.apps import AppConfig


class VotesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.votes"
    label = "votes"
    verbose_name = "Votes (generic up/down on Post or Comment)"

    def ready(self) -> None:
        from . import signals  # noqa: F401

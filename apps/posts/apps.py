from django.apps import AppConfig


class PostsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.posts"
    label = "posts"
    verbose_name = "Posts (feed + share)"

    def ready(self) -> None:
        # Wires up post_save signal handlers in signals.py
        from . import signals  # noqa: F401

"""Test settings — fast, hermetic, no Redis required."""

from .base import *  # noqa: F401, F403

DEBUG = False
ALLOWED_HOSTS = ["*"]

# InMemoryChannelLayer lets consumer tests run without Redis in CI
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# Fast hasher — passwords aren't actually used (set_unusable_password) but Django
# still computes hashes during AbstractBaseUser save.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Speed up tests
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

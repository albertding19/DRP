"""Abstract base models shared across apps.

These never have their own tables — they're meant to be subclassed.
"""

from __future__ import annotations

from django.db import models


class TimeStampedModel(models.Model):
    """Adds `created_at` (indexed) and `updated_at` to any model.

    `created_at` is indexed because feed ordering depends on it.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class _NotDeletedManager(models.Manager):
    """Default manager that hides soft-deleted rows."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class SoftDeletableModel(models.Model):
    """Soft-delete pattern: set `is_deleted=True` instead of removing rows.

    `objects` returns only live rows; `all_objects` returns everything.
    """

    is_deleted = models.BooleanField(default=False, db_index=True)

    objects = _NotDeletedManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.save(update_fields=["is_deleted"])

"""Tag model — roll-own (not django-taggit).

Tags are simple noun-phrase labels users attach to posts. They're
case-insensitive, deduplicated by slug, and decay into kebab-case for
URLs.

Why roll-own:
- django-taggit pulls in an opaque dependency with its own admin and
  ContentType machinery — overkill for a single Post.tags relation.
- ~30 lines here vs. a 1500-line dep.
"""

from __future__ import annotations

from django.db import models
from django.utils.text import slugify

TAG_MAX_LEN = 32
TAG_NAME_MAX_LEN = 48


class Tag(models.Model):
    """A label attached to one or more posts.

    `post_count` is a denormalised counter maintained by an m2m_changed
    signal on Post.tags. It's used to surface popular tags + sort tag
    lists.
    """

    slug = models.SlugField(max_length=TAG_MAX_LEN, unique=True, db_index=True)
    name = models.CharField(max_length=TAG_NAME_MAX_LEN)
    post_count = models.IntegerField(default=0)

    class Meta:
        ordering = ["-post_count", "name"]
        indexes = [
            models.Index(fields=["-post_count"]),
        ]

    def __str__(self) -> str:
        return self.name


def normalise_tag_name(raw: str) -> tuple[str, str]:
    """Return (display_name, slug) from a raw user-typed tag.

    - strips, trims, normalises whitespace
    - slugifies to kebab-case
    - returns ('', '') for empty / pure-whitespace input
    """
    name = " ".join((raw or "").split()).strip()
    if not name:
        return ("", "")
    slug = slugify(name)[:TAG_MAX_LEN]
    if not slug:  # all non-ascii dropped to nothing
        return ("", "")
    return (name[:TAG_NAME_MAX_LEN], slug)

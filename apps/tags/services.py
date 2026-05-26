"""Tag service — the only place that creates Tag rows."""

from __future__ import annotations

from .models import Tag, normalise_tag_name


def parse_tags_input(raw: str | None) -> list[tuple[str, str]]:
    """Parse a comma-separated user input into deduplicated (name, slug) pairs.

    Returns a list preserving the order the user typed (deduped on slug).
    Empty / whitespace-only entries are dropped.
    """
    if not raw:
        return []
    seen_slugs: set[str] = set()
    pairs: list[tuple[str, str]] = []
    for chunk in raw.split(","):
        name, slug = normalise_tag_name(chunk)
        if not slug or slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        pairs.append((name, slug))
    return pairs


def get_or_create_tags(names: list[str]) -> list[Tag]:
    """Resolve / create Tag rows for the given input names.

    `names` can be raw user-typed strings (with mixed casing, whitespace).
    Output Tag list is in the same order as the input names, dedup'd by slug.
    """
    if not names:
        return []
    parsed = parse_tags_input(",".join(names))
    if not parsed:
        return []

    slugs = [slug for _, slug in parsed]
    existing = {t.slug: t for t in Tag.objects.filter(slug__in=slugs)}

    to_create = [Tag(slug=slug, name=name) for name, slug in parsed if slug not in existing]
    if to_create:
        Tag.objects.bulk_create(to_create, ignore_conflicts=True)
        # bulk_create with ignore_conflicts doesn't return pks reliably across
        # backends, so re-fetch to be safe.
        fresh = {t.slug: t for t in Tag.objects.filter(slug__in=[t.slug for t in to_create])}
        existing.update(fresh)

    return [existing[slug] for _, slug in parsed if slug in existing]

"""Moderation services.

Three callables used by the form `clean_*` methods:

  contains_abusive_language(text) -> bool   (L1 — deterministic keyword check)
  judge_with_claude(text) -> (bool, str)    (L2 — Claude Haiku judge)
  log_block(*, author, layer, surface, text, reason)  (writes ModerationLog row)

The L1 check is a thin wrapper over `better-profanity`. The heavy lifting is
its curated wordlist + obfuscation handling; the only project-specific
control surface is `EXTRA_BANNED`, which is empty at ship time and grows as
the team reviews `ModerationLog` rows marked `false_positive=False`.

The L2 judge sends the content + an ADHD-calibrated system prompt to Claude
Haiku and parses the structured JSON response. Fails open on any error so a
peer-support forum never silently goes offline because Anthropic had a blip.
"""

from __future__ import annotations

import json
import logging

from better_profanity import profanity
from django.conf import settings

from .models import ModerationLog
from .prompts import JUDGE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Team-curated additions to the default wordlist. Empty at ship; populate
# based on M3 user-feedback sessions and admin review of ModerationLog rows.
EXTRA_BANNED: set[str] = set()

# `better-profanity` reads its wordlist once at import time. Re-call when
# we want to apply EXTRA_BANNED. Keeping this at module level means tests
# that mutate EXTRA_BANNED need to call `_reload_wordlist()`.
profanity.load_censor_words(custom_words=list(EXTRA_BANNED))


def _reload_wordlist() -> None:
    """Re-apply the wordlist. Useful for tests that mutate EXTRA_BANNED."""
    profanity.load_censor_words(custom_words=list(EXTRA_BANNED))


# Public user-facing message for L1 blocks. Supportive tone — matches the
# peer-support brand voice and avoids pathologising the author.
BLOCK_MESSAGE_L1 = (
    "This contains language we don't allow on Unmasked. "
    "Please rephrase — the community is here to support each other."
)


def contains_abusive_language(text: str) -> bool:
    """True if `text` contains any banned term.

    Case-insensitive; basic obfuscation (l33t-speak, spacing) is handled by
    better-profanity. Returns False for empty/None input.
    """
    if not text:
        return False
    return profanity.contains_profanity(text)


def judge_with_claude(text: str) -> tuple[bool, str]:
    """L2 — send `text` to Claude Haiku with the ADHD-calibrated rubric.

    Returns `(should_block, user_facing_reason)`. The reason is whatever
    Claude generated and is meant to be shown to the user verbatim.

    Fail-open semantics: any of the following return `(False, "")` so the
    submission is allowed through (L1 still ran, L3 still catches):
      - `settings.ANTHROPIC_API_KEY` is empty
      - `text` is empty / whitespace only
      - the `anthropic` SDK raises any exception
      - the API call exceeds `settings.MODERATION_CLAUDE_TIMEOUT_S`
      - Claude returns malformed JSON

    Each non-trivial failure is logged at WARNING level so admins can see
    L2 outages without users being affected.
    """
    if not (text or "").strip():
        return False, ""

    api_key = getattr(settings, "ANTHROPIC_API_KEY", "") or ""
    if not api_key:
        return False, ""

    try:
        # Imported lazily so unit tests that monkeypatch this whole function
        # don't pay the import cost, and so the dep is only loaded when
        # actually needed.
        import anthropic

        client = anthropic.Anthropic(
            api_key=api_key,
            timeout=getattr(settings, "MODERATION_CLAUDE_TIMEOUT_S", 3.0),
        )
        message = client.messages.create(
            model=getattr(settings, "MODERATION_CLAUDE_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=200,
            system=JUDGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        # Claude messages API returns a list of content blocks; we want the
        # first text block.
        raw = ""
        for block in message.content:
            if getattr(block, "type", None) == "text":
                raw = block.text
                break
        if not raw:
            logger.warning("Claude L2 judge returned no text content")
            return False, ""

        parsed = json.loads(raw)
        block = bool(parsed.get("block", False))
        reason = str(parsed.get("reason", "") or "").strip()
        return block, reason
    except json.JSONDecodeError as exc:
        logger.warning("Claude L2 judge returned non-JSON: %s", exc)
        return False, ""
    except Exception as exc:  # noqa: BLE001
        # Catch everything: network errors, anthropic-side errors, timeouts.
        # The whole point of fail-open is that L2 cannot take the site down.
        logger.warning("Claude L2 judge failed: %s", exc)
        return False, ""


def screen(text: str, *, author, surface: str) -> tuple[bool, str]:  # type: ignore[no-untyped-def]
    """Run L1 then L2 on `text`. Single entrypoint for the form layer.

    Returns `(should_block, user_facing_reason)`. Side effect: writes a
    `ModerationLog` row whenever a layer blocks.

    Form `clean_*` methods should:
        block, reason = screen(text, author=self.author, surface=...)
        if block:
            raise ValidationError(reason)

    The caller decides what to do with `reason`; this function never
    re-raises ValidationError itself so it stays a pure service.
    """
    if contains_abusive_language(text):
        log_block(
            author=author,
            layer=ModerationLog.LAYER_L1,
            surface=surface,
            text=text,
            reason=BLOCK_MESSAGE_L1,
        )
        return True, BLOCK_MESSAGE_L1

    block, reason = judge_with_claude(text)
    if block:
        # Claude returned an empty reason? Use a generic supportive fallback
        # so the user isn't told "you've been blocked" with no explanation.
        message = reason or BLOCK_MESSAGE_L1
        log_block(
            author=author,
            layer=ModerationLog.LAYER_L2,
            surface=surface,
            text=text,
            reason=message,
        )
        return True, message

    return False, ""


def log_block(
    *,
    author,  # type: ignore[no-untyped-def]  # apps.accounts.User | AnonymousUser
    layer: str,
    surface: str,
    text: str,
    reason: str,
) -> ModerationLog:
    """Write a single audit row for an L1 or L2 block.

    Author may be `None` (e.g. unauthenticated form submission caught by L1
    via an alternate path); the FK is nullable to allow that.
    """
    # Anonymous users have `is_authenticated=False`. We persist them as
    # null FK so the log doesn't end up referencing a non-existent row.
    author_for_log = author if getattr(author, "is_authenticated", False) else None
    return ModerationLog.objects.create(
        author=author_for_log,
        layer=layer,
        surface=surface,
        text=text,
        reason=reason,
    )

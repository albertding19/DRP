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


def _strip_markdown_fence(text: str) -> str:
    """Strip ``` or ```json fences from a Claude response so the inner
    JSON parses. Tolerant: returns input unchanged if no fence detected.

    Strips the OPENING fence; trailing content (closing fence + any
    commentary Claude appends) is left for `_parse_lenient_json` to ignore.
    """
    s = text.strip()
    if s.startswith("```"):
        # Drop the opening fence line (could be "```" or "```json").
        s = s.split("\n", 1)[-1] if "\n" in s else s[3:]
    return s


def _parse_lenient_json(text: str) -> dict | None:
    """Parse the first JSON object inside `text`, ignoring anything after.

    Returns the parsed dict, or None if no valid JSON object can be
    located. Tolerates leading whitespace + leading commentary before the
    JSON, and any trailing content (closing markdown fence, extra
    explanation) after the JSON object.
    """
    start = text.find("{")
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


# Tool schema used to force structured output from Claude. Combined with
# `tool_choice={"type": "tool", "name": ...}` below, Claude is forced to
# produce a `tool_use` block whose `input` is already a Python dict —
# no JSON parsing, no markdown stripping, no commentary handling needed.
MODERATION_TOOL = {
    "name": "submit_moderation_decision",
    "description": (
        "Submit the final moderation decision for the user-submitted content. "
        "`block` is True if the content violates the rubric. "
        "`reason` is the one-sentence supportive message shown to the user "
        "when blocked (empty string when not blocking)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "block": {
                "type": "boolean",
                "description": "Whether to block this content.",
            },
            "reason": {
                "type": "string",
                "description": (
                    "One short, supportive sentence shown to the user when blocked, "
                    "or empty string when not blocking."
                ),
            },
        },
        "required": ["block", "reason"],
    },
}


def judge_with_claude(text: str) -> tuple[bool, str]:
    """L2 — send `text` to Claude with the ADHD-calibrated rubric.

    Returns `(should_block, user_facing_reason)`. The reason is whatever
    Claude generated and is meant to be shown to the user verbatim.

    Three Sonnet-tier latency optimizations are stacked here, all of which
    also help Haiku marginally:

      1. **Prompt caching** — the system prompt (≈500 input tokens of
         rubric) is marked `cache_control: ephemeral` so subsequent calls
         within ~5 minutes reuse the cached prefix instead of reprocessing.
         Cold start unchanged; warm requests ~3-5× faster on system-prompt
         processing AND ~90% cheaper on cached input tokens.

      2. **Tool-use forced via `tool_choice`** — Claude returns a
         structured `tool_use` block whose `input` is already a dict. No
         markdown wrappers, no trailing commentary, no JSON parsing.
         Eliminates the entire class of parsing bugs and saves ~50-100 ms
         of free-text generation.

      3. **`max_tokens=80`** — caps the worst-case generation time. The
         tool-use payload for our schema is ~30 tokens; 80 leaves headroom
         for a one-sentence rationale and protects against pathological
         long outputs.

    Fail-open semantics unchanged: any error path (missing key, empty
    text, SDK exception, timeout, missing tool_use block, unparseable
    fallback text) returns `(False, "")` so a peer-support forum never
    silently goes offline.
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
            max_tokens=80,
            # Wrap the system prompt as a list with cache_control. The
            # rubric is identical on every call, so Anthropic caches the
            # processed prefix and reuses it across requests within
            # the cache TTL.
            system=[
                {
                    "type": "text",
                    "text": JUDGE_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=[MODERATION_TOOL],
            # Force Claude to call exactly this tool — never free-text.
            tool_choice={"type": "tool", "name": MODERATION_TOOL["name"]},
            messages=[{"role": "user", "content": text}],
        )

        # Find the forced tool_use block. tool_choice guarantees its
        # presence, but we still defend against weird response shapes.
        for content_block in message.content:
            if getattr(content_block, "type", None) == "tool_use":
                payload = content_block.input or {}
                block = bool(payload.get("block", False))
                reason = str(payload.get("reason", "") or "").strip()
                return block, reason

        # Defensive fallback — if for some reason Claude returns text
        # instead of a tool_use block (shouldn't happen with forced
        # tool_choice, but we leave the parser in place for safety),
        # try the lenient JSON path.
        for content_block in message.content:
            if getattr(content_block, "type", None) == "text":
                parsed = _parse_lenient_json(_strip_markdown_fence(content_block.text))
                if parsed is not None:
                    block = bool(parsed.get("block", False))
                    reason = str(parsed.get("reason", "") or "").strip()
                    return block, reason

        logger.warning("Claude L2 judge returned no usable content block: %r", message.content)
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

"""Tests for `judge_with_claude` — L2 Claude Haiku judge.

The autouse fixture in `conftest.py` neutralises the live call for tests
in the wider suite. These tests bypass it because they import
`judge_with_claude` directly (binding the local name at import time, before
the autouse patches the module attribute), and they mock `anthropic.Anthropic`
itself rather than the wrapper.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.moderation.services import _strip_markdown_fence, judge_with_claude


def _make_message(text_block: str):
    """Build a fake `anthropic.types.Message` shape with one text content block."""
    block = MagicMock()
    block.type = "text"
    block.text = text_block
    msg = MagicMock()
    msg.content = [block]
    return msg


class TestStripMarkdownFence:
    """Defensive parser-helper — Claude sometimes wraps JSON in code fences
    despite the rubric asking for raw JSON. Observed behaviour on
    claude-haiku-4-5-20251001."""

    def test_no_fence_returns_unchanged(self):
        assert _strip_markdown_fence('{"block": true}') == '{"block": true}'

    def test_plain_fence(self):
        wrapped = '```\n{"block": true}\n```'
        assert _strip_markdown_fence(wrapped) == '{"block": true}'

    def test_json_fence(self):
        wrapped = '```json\n{"block": false, "reason": ""}\n```'
        assert _strip_markdown_fence(wrapped) == '{"block": false, "reason": ""}'

    def test_fence_with_surrounding_whitespace(self):
        wrapped = '  \n```json\n{"block": true}\n```\n  '
        assert _strip_markdown_fence(wrapped) == '{"block": true}'

    def test_empty_input(self):
        assert _strip_markdown_fence("") == ""


class TestJudgeParsing:
    """The judge correctly parses Claude's JSON response."""

    def test_block_true_with_reason(self, settings):
        settings.ANTHROPIC_API_KEY = "sk-test"
        fake_client = MagicMock()
        fake_client.messages.create.return_value = _make_message(
            '{"block": true, "reason": "This contains a slur."}'
        )
        with patch("anthropic.Anthropic", return_value=fake_client):
            block, reason = judge_with_claude("some content")
        assert block is True
        assert reason == "This contains a slur."

    def test_block_true_with_markdown_fence(self, settings):
        """The real-world case: Claude wraps JSON in ```json … ```."""
        settings.ANTHROPIC_API_KEY = "sk-test"
        fake_client = MagicMock()
        fake_client.messages.create.return_value = _make_message(
            '```json\n{"block": true, "reason": "Spam detected."}\n```'
        )
        with patch("anthropic.Anthropic", return_value=fake_client):
            block, reason = judge_with_claude("some content")
        assert block is True
        assert reason == "Spam detected."

    def test_block_false_clean(self, settings):
        settings.ANTHROPIC_API_KEY = "sk-test"
        fake_client = MagicMock()
        fake_client.messages.create.return_value = _make_message('{"block": false, "reason": ""}')
        with patch("anthropic.Anthropic", return_value=fake_client):
            block, reason = judge_with_claude("clean content")
        assert block is False
        assert reason == ""

    def test_missing_keys_default_to_safe(self, settings):
        """If Claude omits one or both keys, we default to allow (fail open)."""
        settings.ANTHROPIC_API_KEY = "sk-test"
        fake_client = MagicMock()
        fake_client.messages.create.return_value = _make_message("{}")
        with patch("anthropic.Anthropic", return_value=fake_client):
            block, reason = judge_with_claude("anything")
        assert block is False
        assert reason == ""


class TestJudgeFailOpen:
    """Failure modes must NEVER block — L1 + L3 are the safety net."""

    def test_empty_key_fails_open(self, settings):
        settings.ANTHROPIC_API_KEY = ""
        block, reason = judge_with_claude("anything")
        assert block is False
        assert reason == ""

    def test_empty_text_fails_open(self, settings):
        settings.ANTHROPIC_API_KEY = "sk-test"
        block, reason = judge_with_claude("")
        assert block is False
        assert reason == ""

    def test_whitespace_only_text_fails_open(self, settings):
        settings.ANTHROPIC_API_KEY = "sk-test"
        block, reason = judge_with_claude("   \n  ")
        assert block is False
        assert reason == ""

    def test_api_exception_fails_open(self, settings):
        settings.ANTHROPIC_API_KEY = "sk-test"
        fake_client = MagicMock()
        fake_client.messages.create.side_effect = RuntimeError("network down")
        with patch("anthropic.Anthropic", return_value=fake_client):
            block, reason = judge_with_claude("anything")
        assert block is False
        assert reason == ""

    def test_malformed_json_fails_open(self, settings):
        settings.ANTHROPIC_API_KEY = "sk-test"
        fake_client = MagicMock()
        fake_client.messages.create.return_value = _make_message("I cannot respond in JSON, sorry.")
        with patch("anthropic.Anthropic", return_value=fake_client):
            block, reason = judge_with_claude("anything")
        assert block is False
        assert reason == ""

    def test_no_text_blocks_in_response_fails_open(self, settings):
        settings.ANTHROPIC_API_KEY = "sk-test"
        msg = MagicMock()
        msg.content = []
        fake_client = MagicMock()
        fake_client.messages.create.return_value = msg
        with patch("anthropic.Anthropic", return_value=fake_client):
            block, reason = judge_with_claude("anything")
        assert block is False
        assert reason == ""


@pytest.mark.live
class TestJudgeLive:
    """Hit the real Anthropic API. Skipped in CI by default; opt in via `-m live`.

    Useful for periodic team re-validation that the rubric still produces
    sensible outputs as the model evolves.
    """

    def test_obvious_slur_blocked(self):
        from django.conf import settings as live_settings

        if not getattr(live_settings, "ANTHROPIC_API_KEY", ""):
            pytest.skip("ANTHROPIC_API_KEY not set")
        block, reason = judge_with_claude("I genuinely hate all gay people and wish they were gone")
        assert block is True
        assert reason

    def test_adhd_frustration_passes(self):
        from django.conf import settings as live_settings

        if not getattr(live_settings, "ANTHROPIC_API_KEY", ""):
            pytest.skip("ANTHROPIC_API_KEY not set")
        block, _ = judge_with_claude("This assignment is literally killing me")
        assert block is False

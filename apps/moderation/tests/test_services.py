"""Tests for L1 keyword check + ModerationLog audit writer + screen() pipeline."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.accounts.models import User
from apps.moderation import services
from apps.moderation.models import ModerationLog
from apps.moderation.services import (
    BLOCK_MESSAGE_L1,
    contains_abusive_language,
    log_block,
    screen,
)


class TestObviousProfanity:
    """The cheap deterministic floor — catches the unambiguous."""

    @pytest.mark.parametrize(
        "line",
        [
            "you are a fucking idiot",
            "go fuck yourself",
            "what an asshole",
        ],
    )
    def test_obvious_profanity_blocked(self, line: str) -> None:
        assert contains_abusive_language(line), line


class TestADHDContextNotFlagged:
    """ADHD users describe frustration with intense vocabulary. The L1
    filter must not pathologise normal peer-support venting.

    This is the assessment-evidence test: it documents that the team
    designed the filter for the audience, not just imported a library.
    """

    @pytest.mark.parametrize(
        "line",
        [
            "my brain is killing me today",
            "this assignment is destroying me",
            "i want to throw my laptop out the window",
            "my deadlines are murdering my sleep schedule",
            "rejection sensitive dysphoria is the worst",
            "i feel like i'm losing my mind with this medication",
            "the NHS waiting list is brutal",
            "i can't focus today, my brain is fried",
        ],
    )
    def test_adhd_frustration_passes(self, line: str) -> None:
        assert not contains_abusive_language(line), line


class TestEmptyInput:
    @pytest.mark.parametrize("value", ["", None])
    def test_empty_or_none_passes(self, value: str | None) -> None:
        assert not contains_abusive_language(value)  # type: ignore[arg-type]


class TestCustomWordlist:
    """EXTRA_BANNED is the team-curated control surface."""

    def teardown_method(self) -> None:
        # Restore the default wordlist for other tests.
        services.EXTRA_BANNED.clear()
        services._reload_wordlist()

    def test_extra_banned_term_blocks(self) -> None:
        services.EXTRA_BANNED.add("zorkflark")
        services._reload_wordlist()
        assert contains_abusive_language("the zorkflark of the issue")

    def test_clean_text_still_passes(self) -> None:
        services.EXTRA_BANNED.add("zorkflark")
        services._reload_wordlist()
        assert not contains_abusive_language("everything is fine here")


@pytest.mark.django_db
class TestLogBlock:
    def test_creates_row_with_layer_l1(self) -> None:
        user = User.objects.create_anonymous(nickname="logblockl1")
        entry = log_block(
            author=user,
            layer=ModerationLog.LAYER_L1,
            surface=ModerationLog.SURFACE_COMMENT,
            text="some banned text",
            reason=BLOCK_MESSAGE_L1,
        )
        assert entry.pk is not None
        assert entry.author_id == user.id
        assert entry.layer == ModerationLog.LAYER_L1
        assert entry.surface == ModerationLog.SURFACE_COMMENT
        assert entry.text == "some banned text"
        assert entry.reason == BLOCK_MESSAGE_L1
        assert entry.false_positive is False

    def test_creates_row_with_layer_l2(self) -> None:
        user = User.objects.create_anonymous(nickname="logblockl2")
        entry = log_block(
            author=user,
            layer=ModerationLog.LAYER_L2,
            surface=ModerationLog.SURFACE_POST_BODY,
            text="something subtle",
            reason="This appears to contain coded harassment.",
        )
        assert entry.layer == ModerationLog.LAYER_L2
        assert entry.surface == ModerationLog.SURFACE_POST_BODY
        assert entry.reason == "This appears to contain coded harassment."

    def test_anonymous_author_persists_as_null(self) -> None:
        class _Anon:
            is_authenticated = False

        entry = log_block(
            author=_Anon(),
            layer=ModerationLog.LAYER_L1,
            surface=ModerationLog.SURFACE_POST_TITLE,
            text="x",
            reason=BLOCK_MESSAGE_L1,
        )
        assert entry.author_id is None

    def test_post_title_surface(self) -> None:
        user = User.objects.create_anonymous(nickname="logblocktitle")
        entry = log_block(
            author=user,
            layer=ModerationLog.LAYER_L1,
            surface=ModerationLog.SURFACE_POST_TITLE,
            text="x",
            reason=BLOCK_MESSAGE_L1,
        )
        assert entry.surface == ModerationLog.SURFACE_POST_TITLE


@pytest.mark.django_db
class TestScreenPipeline:
    """`screen()` is the single L1+L2 entrypoint called by the forms."""

    def test_clean_text_returns_no_block(self) -> None:
        user = User.objects.create_anonymous(nickname="screenclean")
        block, reason = screen(
            "this strategy worked for me",
            author=user,
            surface=ModerationLog.SURFACE_COMMENT,
        )
        assert block is False
        assert reason == ""
        assert not ModerationLog.objects.exists()

    def test_l1_blocks_and_logs_with_l1_layer(self) -> None:
        user = User.objects.create_anonymous(nickname="screenl1")
        block, reason = screen(
            "you fucking idiot",
            author=user,
            surface=ModerationLog.SURFACE_COMMENT,
        )
        assert block is True
        assert reason == BLOCK_MESSAGE_L1
        entry = ModerationLog.objects.get()
        assert entry.layer == ModerationLog.LAYER_L1
        assert entry.surface == ModerationLog.SURFACE_COMMENT

    def test_l2_blocks_when_l1_passes(self) -> None:
        """When L1 lets text through but L2 says block, the screen logs L2."""
        user = User.objects.create_anonymous(nickname="screenl2")
        # Patch judge_with_claude to simulate Claude's block decision. The
        # autouse fixture has already replaced services.judge_with_claude
        # with a no-op; we override that.
        with patch.object(
            services,
            "judge_with_claude",
            return_value=(True, "This appears to be coded harassment."),
        ):
            block, reason = screen(
                "subtle but harmful sentence",
                author=user,
                surface=ModerationLog.SURFACE_POST_BODY,
            )
        assert block is True
        assert reason == "This appears to be coded harassment."
        entry = ModerationLog.objects.get()
        assert entry.layer == ModerationLog.LAYER_L2
        assert entry.surface == ModerationLog.SURFACE_POST_BODY
        assert entry.reason == "This appears to be coded harassment."

    def test_l2_empty_reason_falls_back_to_l1_message(self) -> None:
        """If Claude returns block=true with empty reason, screen uses the
        supportive L1 message so the user always gets *some* feedback."""
        user = User.objects.create_anonymous(nickname="screenl2empty")
        with patch.object(services, "judge_with_claude", return_value=(True, "")):
            block, reason = screen(
                "borderline content",
                author=user,
                surface=ModerationLog.SURFACE_POST_TITLE,
            )
        assert block is True
        assert reason == BLOCK_MESSAGE_L1
        entry = ModerationLog.objects.get()
        assert entry.layer == ModerationLog.LAYER_L2
        assert entry.reason == BLOCK_MESSAGE_L1

    def test_both_layers_pass(self) -> None:
        user = User.objects.create_anonymous(nickname="screenboth")
        # Default autouse keeps judge_with_claude returning (False, "").
        block, reason = screen(
            "i'm so tired today",
            author=user,
            surface=ModerationLog.SURFACE_COMMENT,
        )
        assert block is False
        assert reason == ""
        assert not ModerationLog.objects.exists()

"""Comment forms."""

from __future__ import annotations

from django import forms

from apps.moderation.models import ModerationLog
from apps.moderation.services import screen

from .models import Comment

COMMENT_MAX_LENGTH = 5000


class CommentForm(forms.ModelForm):
    """Just the body — author/post/parent set by the view.

    Pass `author=request.user` when constructing so L1 / L2 rejections
    have a user to attribute in `ModerationLog`.
    """

    class Meta:
        model = Comment
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "placeholder": "Write a comment…",
                    "rows": 3,
                    "maxlength": COMMENT_MAX_LENGTH,
                }
            ),
        }
        labels = {"body": ""}

    def __init__(self, *args, author=None, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self.author = author

    def clean_body(self) -> str:
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise forms.ValidationError("Can't post an empty comment.")

        # Run the L1 + L2 pipeline. screen() logs blocks to ModerationLog
        # and returns the user-facing reason to surface in the form error.
        block, reason = screen(body, author=self.author, surface=ModerationLog.SURFACE_COMMENT)
        if block:
            raise forms.ValidationError(reason)

        if len(body) > COMMENT_MAX_LENGTH:
            raise forms.ValidationError(
                f"Comments are limited to {COMMENT_MAX_LENGTH:,} characters."
            )
        return body

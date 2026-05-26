"""Comment forms."""

from __future__ import annotations

from django import forms

from .models import Comment

COMMENT_MAX_LENGTH = 5000


class CommentForm(forms.ModelForm):
    """Just the body — author/post/parent set by the view."""

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

    def clean_body(self) -> str:
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise forms.ValidationError("Can't post an empty comment.")
        if len(body) > COMMENT_MAX_LENGTH:
            raise forms.ValidationError(
                f"Comments are limited to {COMMENT_MAX_LENGTH:,} characters."
            )
        return body

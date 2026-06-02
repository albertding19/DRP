"""Forms for post create / edit."""

from __future__ import annotations

from django import forms

from apps.moderation.models import ModerationLog
from apps.moderation.services import screen
from apps.tags.services import parse_tags_input

from .models import Post


class PostForm(forms.ModelForm):
    """The Share form. Tags entered as comma-separated; parsed/normalised on clean.

    Pass `author=request.user` when constructing so L1 / L2 rejections
    have a user to attribute in `ModerationLog`.
    """

    tags = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "placeholder": "comma, separated, tags",
                "autocomplete": "off",
            }
        ),
        help_text="Optional. Comma-separated. Max 5 tags.",
    )

    class Meta:
        model = Post
        fields = ["post_type", "title", "body"]
        widgets = {
            "post_type": forms.RadioSelect(),
            "title": forms.TextInput(
                attrs={
                    "placeholder": "What's it about?",
                    "maxlength": 200,
                    "autocomplete": "off",
                    "autofocus": "autofocus",
                }
            ),
            "body": forms.Textarea(
                attrs={
                    "placeholder": (
                        "Share the strategy that worked, or the problem you're stuck on."
                    ),
                    "rows": 6,
                }
            ),
        }
        labels = {
            "post_type": "What kind of post is this?",
            "title": "Title",
            "body": "Body",
        }

    def __init__(self, *args, author=None, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self.author = author

    def clean_title(self) -> str:
        title = (self.cleaned_data["title"] or "").strip()
        if not title:
            raise forms.ValidationError("Give your post a title.")

        block, reason = screen(title, author=self.author, surface=ModerationLog.SURFACE_POST_TITLE)
        if block:
            raise forms.ValidationError(reason)

        return title

    def clean_body(self) -> str:
        body = (self.cleaned_data["body"] or "").strip()
        if not body:
            raise forms.ValidationError("Body can't be empty.")

        block, reason = screen(body, author=self.author, surface=ModerationLog.SURFACE_POST_BODY)
        if block:
            raise forms.ValidationError(reason)

        return body

    def clean_tags(self) -> list[str]:
        raw = self.cleaned_data.get("tags", "")
        parsed = parse_tags_input(raw)
        if len(parsed) > 5:
            raise forms.ValidationError("At most 5 tags allowed.")
        # Return the display-name strings; service does the slug dedup.
        return [name for name, _slug in parsed]

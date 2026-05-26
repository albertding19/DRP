"""Forms for post create / edit."""

from __future__ import annotations

from django import forms

from .models import Post


class PostForm(forms.ModelForm):
    """The Share form. Tags will land in M3."""

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

    def clean_title(self) -> str:
        title = (self.cleaned_data["title"] or "").strip()
        if not title:
            raise forms.ValidationError("Give your post a title.")
        return title

    def clean_body(self) -> str:
        body = (self.cleaned_data["body"] or "").strip()
        if not body:
            raise forms.ValidationError("Body can't be empty.")
        return body

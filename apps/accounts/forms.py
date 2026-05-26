"""Forms for nickname signup."""

from __future__ import annotations

from django import forms

from .models import User, validate_nickname


class NicknamePickForm(forms.Form):
    nickname = forms.CharField(
        max_length=24,
        min_length=3,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Pick a nickname",
                "autofocus": "autofocus",
                "autocomplete": "off",
                "autocapitalize": "none",
                "spellcheck": "false",
            }
        ),
    )

    def clean_nickname(self) -> str:
        nickname = (self.cleaned_data["nickname"] or "").strip()
        validate_nickname(nickname)
        if User.objects.filter(nickname=nickname).exists():
            raise forms.ValidationError("That nickname's taken — try another.")
        return nickname

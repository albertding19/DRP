"""Forms for auth flows.

Each form is a thin Django Form; validation logic that touches the
database (uniqueness, taken-by-someone-else) lives here so the view
stays a flat sequence of `if form.is_valid(): service_call()`.
"""

from __future__ import annotations

from django import forms

from .models import User, validate_nickname


class EmailSignInForm(forms.Form):
    """The unified welcome-page form. Just an email address.

    We do NOT distinguish login vs signup here — the service layer's
    `find_or_create_user_for_email` does that automatically when the
    user clicks the magic link.
    """

    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "placeholder": "you@example.com",
                "autofocus": "autofocus",
                "autocomplete": "email",
                "spellcheck": "false",
            }
        ),
    )

    def clean_email(self) -> str:
        return (self.cleaned_data.get("email") or "").strip().lower()


class ClaimEmailForm(forms.Form):
    """For existing nickname-only users adding an email. We re-use the
    same uniqueness check as the welcome page so callers can `add_error`
    on the right field if the email is already in use."""

    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "placeholder": "you@example.com",
                "autofocus": "autofocus",
                "autocomplete": "email",
                "spellcheck": "false",
            }
        ),
    )

    def clean_email(self) -> str:
        return (self.cleaned_data.get("email") or "").strip().lower()


class SettingsNicknameForm(forms.Form):
    """Change-nickname form on the settings page. Immediate save — no
    verification step (nickname is display only)."""

    nickname = forms.CharField(
        max_length=24,
        min_length=3,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "off",
                "autocapitalize": "none",
                "spellcheck": "false",
            }
        ),
    )

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_user = current_user

    def clean_nickname(self) -> str:
        nickname = (self.cleaned_data["nickname"] or "").strip()
        validate_nickname(nickname)
        # Allow the current user to "change" to their own nickname (no-op).
        qs = User.objects.filter(nickname=nickname)
        if self.current_user is not None:
            qs = qs.exclude(pk=self.current_user.pk)
        if qs.exists():
            raise forms.ValidationError("That nickname's taken — try another.")
        return nickname


class SettingsEmailForm(forms.Form):
    """Change-email form on the settings page. The form just validates;
    the verification email is sent by the view via
    `services.request_email_change`."""

    email = forms.EmailField(widget=forms.EmailInput(attrs={"autocomplete": "email"}))

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_user = current_user

    def clean_email(self) -> str:
        email = (self.cleaned_data.get("email") or "").strip().lower()
        qs = User.objects.filter(email=email)
        if self.current_user is not None:
            qs = qs.exclude(pk=self.current_user.pk)
        if qs.exists():
            raise forms.ValidationError("That email's already in use.")
        return email


# Kept around so `apps.accounts.views.start`'s legacy GET (if anyone still
# hits the old URL after the rebrand) can still render. Plus the admin
# shell may use it. Not exposed in the new welcome page.
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

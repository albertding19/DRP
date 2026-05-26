"""Vote view — HTMX endpoint.

POST /vote/<target_type>/<object_id>/  body: value=1 | -1
Returns the rendered _vote_buttons.html partial with the new score.

`target_type` is 'post' or 'comment'. We map it to a ContentType to look
up the target instance, then call `cast_vote`.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .services import InvalidVoteValue, cast_vote

# Allow-list of votable types — protects against an attacker posting an
# arbitrary content_type label and casting votes on User rows or similar.
_VOTABLE_TYPES: dict[str, tuple[str, str]] = {
    "post": ("posts", "post"),
    "comment": ("comments", "comment"),
}


@login_required
@require_POST
def cast(request: HttpRequest, target_type: str, object_id: int) -> HttpResponse:
    if target_type not in _VOTABLE_TYPES:
        return HttpResponseBadRequest(f"Unknown target type: {target_type!r}")

    app_label, model_name = _VOTABLE_TYPES[target_type]
    ct = ContentType.objects.get(app_label=app_label, model=model_name)
    target_class = ct.model_class()
    target = get_object_or_404(target_class, pk=object_id)

    try:
        value = int(request.POST.get("value", ""))
    except (TypeError, ValueError):
        return HttpResponseBadRequest("Missing or non-integer 'value'.")

    try:
        new_score, user_vote = cast_vote(user=request.user, target=target, value=value)
    except InvalidVoteValue as exc:
        return HttpResponseBadRequest(str(exc))

    return render(
        request,
        "votes/_vote_buttons.html",
        {
            "target": target,
            "target_type": target_type,
            "score": new_score,
            "user_vote": user_vote,
        },
    )

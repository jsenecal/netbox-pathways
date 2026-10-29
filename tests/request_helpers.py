"""Request-side helpers shared by the API and map view tests."""

import json
import re
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory
from rest_framework.test import APIClient

from netbox_pathways.views import MapView


def api_client_for(user):
    """An API client authenticated as `user`, re-fetched so no stale permission cache rides along."""
    client = APIClient()
    client.force_authenticate(user=get_user_model().objects.get(pk=user.pk))
    return client


def user_with_view_permission(username, model, constraints=None):
    """A non-superuser whose only permission is `view` on `model`, optionally constrained."""
    from users.models import ObjectPermission

    user = get_user_model().objects.create_user(username=username, password="x")  # noqa: S106
    perm = ObjectPermission.objects.create(
        name=f"{username}-view",
        enabled=True,
        actions=["view"],
        constraints=constraints,
    )
    perm.object_types.set([ContentType.objects.get_for_model(model)])
    perm.users.add(user)
    return user


def parse_json_script(content, element_id):
    """Extract and parse the payload of a Django `json_script` tag."""
    match = re.search(
        rf'<script id="{element_id}" type="application/json">(.*?)</script>',
        content,
        re.DOTALL,
    )
    assert match, f"no json_script tag with id={element_id!r} in the response"
    return json.loads(match.group(1))


def render_map(query_string="", *, user=None, extent=None, feature_extent=None):
    """Render MapView.get() and return the response body.

    `extent` stands in for the trimmed data extent. When `feature_extent` is
    given, a `?select=` value resolves to a stand-in object with that bbox
    instead of being looked up in the database.
    """
    request = RequestFactory().get(f"/plugins/pathways/map/?{query_string}")
    request.user = user or AnonymousUser()
    with ExitStack() as stack:
        stack.enter_context(patch.object(MapView, "_data_extent", return_value=extent))
        if feature_extent is not None:
            stack.enter_context(
                patch.object(
                    MapView,
                    "_resolve_selection",
                    side_effect=lambda param, user: SimpleNamespace(map_select_id=param),
                )
            )
            stack.enter_context(patch.object(MapView, "_feature_extent", return_value=feature_extent))
        return MapView().get(request).content.decode()

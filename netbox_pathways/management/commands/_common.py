"""Arguments and helpers shared by the plugin's data-rewriting commands.

Those commands preview by default and write only with `--apply`. Writes made
inside NetBox's event pipeline get change-log entries and fire webhooks/event
rules; outside it they bypass both, so the commands offer `--user` to opt in.
"""

import uuid
from contextlib import contextmanager

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from netbox.context_managers import event_tracking
from utilities.request import NetBoxFakeRequest


def add_apply_argument(parser, help_text):
    parser.add_argument("--apply", action="store_true", help=help_text)


def resolve_structures(pks):
    """The structures with these PKs; a CommandError names any that do not exist."""
    from netbox_pathways.models import Structure

    structures = list(Structure.objects.filter(pk__in=pks))
    missing = set(pks) - {structure.pk for structure in structures}
    if missing:
        raise CommandError(f"Structure PK(s) not found: {sorted(missing)}")
    return structures


def add_user_argument(parser, action):
    parser.add_argument(
        "--user",
        metavar="USERNAME",
        help=(
            f"NetBox username to attribute the {action} to. When given, --apply runs "
            "inside NetBox's event pipeline: change-log entries are recorded and "
            f"webhooks/event rules fire. Without it the {action} bypasses the pipeline."
        ),
    )


def resolve_user(username):
    if not username:
        return None
    user_model = get_user_model()
    try:
        return user_model.objects.get(username=username)
    except user_model.DoesNotExist:
        raise CommandError(f"User '{username}' does not exist.") from None


@contextmanager
def tracked(user):
    """Run the block inside NetBox's event pipeline when a user is given."""
    if user is None:
        yield
        return
    request = NetBoxFakeRequest(
        {
            "META": {},
            "COOKIES": {},
            "POST": {},
            "GET": {},
            "FILES": {},
            "user": user,
            "method": "POST",
            "path": "",
            "id": uuid.uuid4(),
        }
    )
    with event_tracking(request):
        yield

"""The single pathway UI surface: navigation quick links, delete protection, the children tab."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory
from django.urls import reverse
from users.models import ObjectPermission

from netbox_pathways.choices import PathwayTypeChoices
from netbox_pathways.models import Pathway
from netbox_pathways.navigation import menu
from netbox_pathways.views import PathwayChildrenView


def test_navigation_has_every_type():
    """Every pathway type has a menu entry opening the list and the add form preset to that type."""
    items = {str(item.url): item for group in menu.groups for item in group.items}
    list_url = reverse("plugins:netbox_pathways:pathway_list")
    add_url = reverse("plugins:netbox_pathways:pathway_add")

    for pathway_type in PathwayTypeChoices.values():
        item = items[f"{list_url}?pathway_type={pathway_type}"]
        assert [str(button.url) for button in item.buttons] == [f"{add_url}?pathway_type={pathway_type}"]


@pytest.mark.django_db
def test_delete_view_reports_protected_children(client, admin_user):
    """Deleting a bank that still holds a conduit is refused without a server error; the leaf deletes."""
    bank = Pathway.objects.create(pathway_type="conduit_bank", label="del-bank")
    conduit = Pathway.objects.create(pathway_type="conduit", label="del-conduit", parent=bank)
    client.force_login(admin_user)

    response = client.post(reverse("plugins:netbox_pathways:pathway_delete", args=[bank.pk]), {"confirm": True})

    assert response.status_code == 302
    assert response.url == bank.get_absolute_url()
    assert Pathway.objects.filter(pk=bank.pk).exists()

    client.post(reverse("plugins:netbox_pathways:pathway_delete", args=[conduit.pk]), {"confirm": True})

    assert not Pathway.objects.filter(pk=conduit.pk).exists()


@pytest.mark.django_db
def test_children_tab_lists_the_whole_subtree_the_user_may_view():
    """A bank's tab counts its conduit and the innerduct inside it, and lists only what the user may view."""
    bank = Pathway.objects.create(pathway_type="conduit_bank", label="tab-bank")
    conduit = Pathway.objects.create(pathway_type="conduit", label="tab-conduit", parent=bank)
    innerduct = Pathway.objects.create(pathway_type="innerduct", label="tab-innerduct", parent=conduit)
    Pathway.objects.create(pathway_type="conduit", label="tab-elsewhere")
    user = get_user_model().objects.create_user(username="tab-innerducts-only")
    permission = ObjectPermission.objects.create(
        name="tab-innerducts-only", actions=["view"], constraints={"pathway_type": "innerduct"}
    )
    permission.object_types.add(ContentType.objects.get_for_model(Pathway))
    permission.users.add(user)
    request = RequestFactory().get("/")
    request.user = user

    assert PathwayChildrenView.tab.badge(bank) == 2
    assert list(PathwayChildrenView().get_children(request, bank)) == [innerduct]

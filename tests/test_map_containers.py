"""The map draws containers only; child pathways resolve to them (issue #166).

Innerducts and conduits inside a bank are never drawn on their own. A
``?select=`` naming one, and a map search matching one, must land on the
outermost drawn container instead.
"""

import pytest
from dcim.models import Site
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.geo import get_srid
from netbox_pathways.models import Conduit, ConduitBank, Innerduct, Structure

from .request_helpers import api_client_for, parse_json_script, render_map, user_with_view_permission


@pytest.fixture
def plant(db):
    srid = get_srid()
    site = Site.objects.create(name="Containers Site", slug="containers-site")
    a, b = (
        Structure.objects.create(
            name=f"Cont-S{i}",
            structure_type="manhole",
            site=site,
            geometry=Point(i * 100, i * 100, srid=srid),
        )
        for i in (1, 2)
    )
    path = LineString((100, 100), (200, 200), srid=srid)
    bank = ConduitBank.objects.create(label="Cont-Bank", start_structure=a, end_structure=b, path=path)
    banked = Conduit.objects.create(
        label="Cont-Banked", conduit_bank=bank, start_structure=a, end_structure=b, path=path
    )
    loose = Conduit.objects.create(label="Cont-Loose", start_structure=a, end_structure=b, path=path)
    return {
        "bank": bank,
        "banked": banked,
        "loose": loose,
        "loose_duct": Innerduct.objects.create(label="Cont-Duct-Loose", parent_conduit=loose, size="32mm"),
        "banked_duct": Innerduct.objects.create(label="Cont-Duct-Banked", parent_conduit=banked, size="32mm"),
    }


class TestMapContainer:
    def test_standalone_conduit_is_its_own_container(self, plant):
        assert plant["loose"].map_container == plant["loose"]

    def test_banked_conduit_resolves_to_its_bank(self, plant):
        assert plant["banked"].map_container == plant["bank"]

    def test_innerduct_resolves_to_its_conduit(self, plant):
        assert plant["loose_duct"].map_container == plant["loose"]

    def test_innerduct_in_a_banked_conduit_resolves_to_the_bank(self, plant):
        assert plant["banked_duct"].map_container == plant["bank"]


def _map_config(user, select):
    return parse_json_script(render_map(f"select={select}", user=user), "pathways-map-init")


class TestMapSelectResolution:
    def test_innerduct_selects_the_bank_and_zooms_to_it(self, plant, admin_user):
        config = _map_config(admin_user, f"innerduct-{plant['banked_duct'].pk}")
        assert config["select"] == f"conduit_bank-{plant['bank'].pk}"
        assert config["bounds"] is not None

    def test_drawn_feature_is_left_alone(self, plant, admin_user):
        config = _map_config(admin_user, f"conduit_bank-{plant['bank'].pk}")
        assert config["select"] == f"conduit_bank-{plant['bank'].pk}"

    def test_unknown_child_is_left_alone(self, plant, admin_user):
        assert _map_config(admin_user, "innerduct-0")["select"] == "innerduct-0"


def _search(client, layer, q):
    resp = client.get(f"/api/plugins/pathways/geo/{layer}/", {"q": q, "format": "json"})
    assert resp.status_code == 200
    return {f["properties"]["label"]: f["properties"].get("search_match") for f in resp.json()["features"]}


class TestGeoChildSearch:
    def test_innerduct_label_finds_its_conduit(self, plant, admin_user):
        assert _search(api_client_for(admin_user), "conduits", "Cont-Duct-Loose") == {"Cont-Loose": "Cont-Duct-Loose"}

    def test_banked_conduit_label_finds_its_bank(self, plant, admin_user):
        assert _search(api_client_for(admin_user), "conduit-banks", "Cont-Banked") == {"Cont-Bank": "Cont-Banked"}

    def test_innerduct_in_a_bank_finds_the_bank(self, plant, admin_user):
        assert _search(api_client_for(admin_user), "conduit-banks", "Cont-Duct-Banked") == {
            "Cont-Bank": "Cont-Duct-Banked"
        }

    def test_own_label_match_carries_no_child_hint(self, plant, admin_user):
        assert _search(api_client_for(admin_user), "conduit-banks", "Cont-Bank") == {"Cont-Bank": None}

    def test_children_the_user_cannot_view_do_not_match(self, plant):
        client = api_client_for(user_with_view_permission("cont-no-ducts", Conduit))
        assert _search(client, "conduits", "Cont-Duct-Loose") == {}

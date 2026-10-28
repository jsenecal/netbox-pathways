"""The map draws containers only; child pathways resolve to them (issues #166, #172).

Innerducts, trays, raceways and any pathway with a parent are never drawn on
their own. A ``?select=`` naming one, and a map search matching one, must land
on the outermost drawn container instead, and only on what the user may view.
"""

import pytest
from dcim.models import Site
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.geo import get_srid
from netbox_pathways.models import Pathway, Structure
from netbox_pathways.views import MapView

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
    route = LineString((100, 100), (200, 200), srid=srid)

    def top(pathway_type, label):
        return Pathway.objects.create(
            pathway_type=pathway_type, label=label, start_structure=a, end_structure=b, geometry=route
        )

    def child(pathway_type, label, parent):
        return Pathway.objects.create(pathway_type=pathway_type, label=label, parent=parent)

    bank = top("conduit_bank", "Cont-Bank")
    banked = child("conduit", "Cont-Banked", bank)
    loose = top("conduit", "Cont-Loose")
    buried = top("direct_buried", "Cont-Buried")
    raceway = top("raceway", "Cont-Raceway")
    return {
        "structure": a,
        "bank": bank,
        "banked": banked,
        "loose": loose,
        "loose_duct": child("innerduct", "Cont-Duct-Loose", loose),
        "banked_duct": child("innerduct", "Cont-Duct-Banked", banked),
        "buried": buried,
        "buried_duct": child("innerduct", "Cont-Duct-Buried", buried),
        "raceway": raceway,
        "raceway_conduit": child("conduit", "Cont-Raceway-Conduit", raceway),
        "submarine": top("submarine", "Cont-Submarine"),
    }


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

    def test_structure_selects_itself(self, plant, admin_user):
        structure = plant["structure"]
        assert structure.map_select_id == f"structure-{structure.pk}"
        assert MapView._resolve_selection(structure.map_select_id, admin_user) == structure

    def test_conduit_in_raceway_is_not_selectable(self, plant, admin_user):
        assert MapView._resolve_selection(f"conduit-{plant['raceway_conduit'].pk}", admin_user) is None

    def test_type_must_match_the_pathway(self, plant, admin_user):
        assert MapView._resolve_selection(f"aerial-{plant['loose'].pk}", admin_user) is None

    @pytest.mark.parametrize("param", ["unknown-123", "noid", "structure-999999", "conduit-x"])
    def test_unresolvable_params(self, plant, admin_user, param):
        assert MapView._resolve_selection(param, admin_user) is None

    def test_container_the_user_cannot_view_is_not_resolved(self, plant):
        """Seeing an innerduct must not reveal the bank it sits in."""
        user = user_with_view_permission("cont-ducts-only", Pathway, {"pathway_type": "innerduct"})
        assert MapView._resolve_selection(f"innerduct-{plant['banked_duct'].pk}", user) is None

    def test_selection_the_user_cannot_view_is_not_resolved(self, plant):
        user = user_with_view_permission("cont-banks-only", Pathway, {"pathway_type": "conduit_bank"})
        assert MapView._resolve_selection(f"innerduct-{plant['banked_duct'].pk}", user) is None


class TestMapConfig:
    def test_legend_lists_the_drawn_types(self, db):
        config = parse_json_script(render_map(), "pathways-config")
        assert config["drawnTypes"] == ["conduit_bank", "conduit", "aerial", "direct_buried", "submarine"]


def _geo(client, **params):
    resp = client.get("/api/plugins/pathways/geo/pathways/", {"format": "json", **params})
    assert resp.status_code == 200
    return {f["properties"]["label"]: f["properties"].get("search_match") for f in resp.json()["features"]}


def _search(client, pathway_type, q):
    return _geo(client, pathway_type=pathway_type, containers="true", q=q)


class TestContainersFilter:
    def test_containers_filter_excludes_children(self, plant, admin_user):
        drawn = {"Cont-Bank", "Cont-Loose", "Cont-Buried", "Cont-Submarine"}
        client = api_client_for(admin_user)
        assert set(_geo(client, containers="true")) == drawn
        # The pathways the containers stand for: children with their own
        # geometry would come back here; the plant's children have none.
        assert set(_geo(client, containers="false")) == {"Cont-Raceway"}

    def test_submarine_is_drawn(self, plant, admin_user):
        client = api_client_for(admin_user)
        assert set(_geo(client, pathway_type="submarine", containers="true")) == {"Cont-Submarine"}
        info = client.get("/api/plugins/pathways/geo/info/", {"format": "json"}).json()
        assert info["counts"]["submarine"] == 1
        assert info["thresholds"]["submarine"] == {"hide": 500}

    def test_info_counts_only_containers(self, plant, admin_user):
        counts = api_client_for(admin_user).get("/api/plugins/pathways/geo/info/", {"format": "json"}).json()["counts"]
        assert (counts["conduit_banks"], counts["conduits"], counts["direct_buried"]) == (1, 1, 1)


class TestGeoChildSearch:
    def test_innerduct_label_finds_its_conduit(self, plant, admin_user):
        assert _search(api_client_for(admin_user), "conduit", "Cont-Duct-Loose") == {"Cont-Loose": "Cont-Duct-Loose"}

    def test_banked_conduit_label_finds_its_bank(self, plant, admin_user):
        assert _search(api_client_for(admin_user), "conduit_bank", "Cont-Banked") == {"Cont-Bank": "Cont-Banked"}

    def test_innerduct_in_a_bank_finds_the_bank(self, plant, admin_user):
        assert _search(api_client_for(admin_user), "conduit_bank", "Cont-Duct-Banked") == {
            "Cont-Bank": "Cont-Duct-Banked"
        }

    def test_innerduct_in_direct_buried_finds_the_direct_buried(self, plant, admin_user):
        assert _search(api_client_for(admin_user), "direct_buried", "Cont-Duct-Buried") == {
            "Cont-Buried": "Cont-Duct-Buried"
        }

    def test_own_label_match_carries_no_child_hint(self, plant, admin_user):
        assert _search(api_client_for(admin_user), "conduit_bank", "Cont-Bank") == {"Cont-Bank": None}

    def test_children_the_user_cannot_view_do_not_match(self, plant):
        """Review focus: map search never reveals a child the user cannot view."""
        client = api_client_for(user_with_view_permission("cont-no-ducts", Pathway, {"pathway_type": "conduit"}))
        assert _search(client, "conduit", "Cont-Duct-Loose") == {}

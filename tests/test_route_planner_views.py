"""Tests for route-planner view helpers."""

from unittest.mock import patch

import pytest
from django.contrib.gis.geos import LineString, Point
from django.test import RequestFactory

from netbox_pathways.geo import get_srid
from netbox_pathways.models import Pathway, PlannedRoute, Structure
from netbox_pathways.views import (
    RoutePlannerConstraintView,
    RoutePlannerFindView,
    RoutePlannerSaveView,
    RoutePlannerView,
)
from tests.conftest import build_cable_with_terminations

SRID = get_srid()

# ---------------------------------------------------------------------------
# RoutePlannerFindView._parse_int_list
# ---------------------------------------------------------------------------


class TestParseIntList:
    def test_none_returns_none(self):
        assert RoutePlannerFindView._parse_int_list(None) is None

    def test_empty_string_returns_none(self):
        assert RoutePlannerFindView._parse_int_list("") is None

    def test_empty_list_returns_none(self):
        assert RoutePlannerFindView._parse_int_list([]) is None

    def test_comma_separated_string(self):
        assert RoutePlannerFindView._parse_int_list("1,2,3") == [1, 2, 3]

    def test_comma_separated_with_whitespace(self):
        assert RoutePlannerFindView._parse_int_list(" 1 , 2 , 3 ") == [1, 2, 3]

    def test_list_of_ints(self):
        assert RoutePlannerFindView._parse_int_list([1, 2, 3]) == [1, 2, 3]

    def test_list_of_strings(self):
        assert RoutePlannerFindView._parse_int_list(["1", "2"]) == [1, 2]

    def test_list_of_comma_separated_strings(self):
        # getlist may return ["1,2", "3"] when multiple form fields share a name
        assert RoutePlannerFindView._parse_int_list(["1,2", "3"]) == [1, 2, 3]

    def test_garbage_in_string_returns_none(self):
        # All-or-nothing on the string path -- mirrors the source's try/except
        assert RoutePlannerFindView._parse_int_list("abc") is None

    def test_garbage_in_list_is_skipped(self):
        # Per-item path tolerates garbage and keeps the valid items
        assert RoutePlannerFindView._parse_int_list(["1", "abc", "2"]) == [1, 2]

    def test_all_garbage_in_list_returns_none(self):
        assert RoutePlannerFindView._parse_int_list(["abc", "def"]) is None


# ---------------------------------------------------------------------------
# RoutePlannerView._resolve_termination
# ---------------------------------------------------------------------------


@pytest.fixture
def view():
    return RoutePlannerView()


@pytest.mark.django_db
class TestResolveTermination:
    @pytest.fixture
    def srid(self):
        return get_srid()

    @pytest.fixture
    def site(self):
        from dcim.models import Site

        return Site.objects.create(name="RP-site", slug="rp-site")

    @pytest.fixture
    def structure(self, site, srid):
        return Structure.objects.create(
            name="RP-struct",
            site=site,
            location=Point(0, 0, srid=srid),
        )

    def test_no_termination_returns_none(self, view):
        # Cable exists but has no CableTermination rows on either end
        from dcim.models import Cable

        cable = Cable.objects.create(label="RP-empty")
        assert view._resolve_termination(cable, "A") is None
        assert view._resolve_termination(cable, "B") is None

    def test_a_side_resolves_to_structure(self, view, site, structure):
        cable = build_cable_with_terminations(label="RP-A", site=site, terminate_a=True, terminate_b=False)
        assert view._resolve_termination(cable, "A") == structure

    def test_b_side_resolves_to_structure(self, view, site, structure):
        cable = build_cable_with_terminations(label="RP-B", site=site, terminate_a=False, terminate_b=True)
        assert view._resolve_termination(cable, "B") == structure


# ---------------------------------------------------------------------------
# RoutePlannerFindView.post
# ---------------------------------------------------------------------------


@pytest.fixture
def factory():
    return RequestFactory()


@pytest.fixture
def two_structures(db):
    s1 = Structure.objects.create(name="A", location=Point(0, 0, srid=SRID))
    s2 = Structure.objects.create(name="B", location=Point(100, 100, srid=SRID))
    return s1, s2


@pytest.mark.django_db
class TestRoutePlannerFindView:
    def test_missing_endpoint_returns_empty_panel(self, factory, admin_user):
        request = factory.post(
            "/pathways/route-planner/find/",
            {"start_structure": "1"},  # end_structure missing
        )
        request.user = admin_user
        response = RoutePlannerFindView().post(request)
        assert response.status_code == 200
        assert b"Select both start and end structures" in response.content

    def test_returns_results_panel_when_engine_returns_path(self, factory, two_structures, admin_user):
        s1, s2 = two_structures
        pw = Pathway.objects.create(
            label="P1",
            pathway_type="conduit",
            path=LineString((0, 0), (100, 100), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )

        request = factory.post(
            "/pathways/route-planner/find/",
            {
                "start_structure": str(s1.pk),
                "end_structure": str(s2.pk),
                "prefer_in_use": "0",
            },
        )
        request.user = admin_user

        with patch(
            "netbox_pathways.route_engine.find_route",
            return_value=(1.0, [pw.pk]),
        ):
            response = RoutePlannerFindView().post(request)

        assert response.status_code == 200
        # Pathway label appears in the rendered planner_results.html fragment
        assert b"P1" in response.content


# ---------------------------------------------------------------------------
# RoutePlannerSaveView.post
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRoutePlannerSaveView:
    def test_creates_planned_route_with_name_and_pathway_ids(self, factory, two_structures, admin_user):
        s1, s2 = two_structures
        pw = Pathway.objects.create(
            label="P1",
            pathway_type="conduit",
            path=LineString((0, 0), (100, 100), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )

        request = factory.post(
            "/pathways/route-planner/save/",
            {
                "pathway_ids": f"{pw.pk}",
                "start_structure": str(s1.pk),
                "end_structure": str(s2.pk),
                "name": "My Plan",
            },
        )
        request.user = admin_user

        response = RoutePlannerSaveView().post(request)
        assert response.status_code == 302  # redirect to detail

        plan = PlannedRoute.objects.get(name="My Plan")
        assert plan.start_structure_id == s1.pk
        assert plan.end_structure_id == s2.pk
        assert plan.pathway_ids == [pw.pk]

    def test_blank_name_defaults_to_unnamed_route(self, factory, two_structures, admin_user):
        s1, s2 = two_structures
        request = factory.post(
            "/pathways/route-planner/save/",
            {
                "pathway_ids": "",
                "start_structure": str(s1.pk),
                "end_structure": str(s2.pk),
                "name": "   ",  # whitespace only
            },
        )
        request.user = admin_user

        RoutePlannerSaveView().post(request)
        assert PlannedRoute.objects.filter(name="Unnamed Route").exists()


# ---------------------------------------------------------------------------
# RoutePlannerConstraintView.get
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRoutePlannerConstraintView:
    def test_unknown_type_returns_400(self, factory, admin_user):
        request = factory.get("/pathways/route-planner/constraint/?type=not_a_type")
        request.user = admin_user
        response = RoutePlannerConstraintView().get(request)
        assert response.status_code == 400

    def test_enum_constraint_excludes_conduit_bank(self, factory, admin_user):
        request = factory.get(
            "/pathways/route-planner/constraint/?type=avoid_pathway_types",
        )
        request.user = admin_user
        response = RoutePlannerConstraintView().get(request)
        assert response.status_code == 200
        body = response.content.decode()
        # PathwayTypeChoices includes "conduit_bank" but the constraint
        # card filters it out -- the planner targets concrete pathways.
        assert "conduit_bank" not in body

    def test_model_constraint_renders_api_select_widget(self, factory, admin_user):
        request = factory.get(
            "/pathways/route-planner/constraint/?type=avoid_structures",
        )
        request.user = admin_user
        response = RoutePlannerConstraintView().get(request)
        assert response.status_code == 200
        body = response.content.decode()
        # Rendered widget must include the api-select hook so the frontend
        # lazy-loads options instead of materializing all rows.
        assert "api-select" in body

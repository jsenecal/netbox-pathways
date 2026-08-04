"""The route planner prefills a cable end only when it is unambiguous."""

import pytest
from django.contrib.gis.geos import Point

from netbox_pathways.geo import get_srid
from netbox_pathways.models import Structure
from netbox_pathways.views import RoutePlannerView
from tests.conftest import build_cable_with_terminations

SRID = get_srid()


@pytest.fixture
def site(db):
    from dcim.models import Site

    return Site.objects.create(name="PP-site", slug="pp-site")


@pytest.mark.django_db
class TestPlannerPrefill:
    def test_prefills_the_only_candidate_structure(self, site):
        structure = Structure.objects.create(name="PP-only", site=site, geometry=Point(0, 0, srid=SRID))
        cable = build_cable_with_terminations(label="PP-one", site=site)
        assert RoutePlannerView()._prefill_structure(cable, "A") == structure

    def test_does_not_guess_between_several_candidates(self, site):
        Structure.objects.create(name="PP-a", site=site, geometry=Point(0, 0, srid=SRID))
        Structure.objects.create(name="PP-b", site=site, geometry=Point(1, 1, srid=SRID))
        cable = build_cable_with_terminations(label="PP-many", site=site)
        assert RoutePlannerView()._prefill_structure(cable, "A") is None

    def test_returns_none_when_nothing_is_modeled(self, site):
        cable = build_cable_with_terminations(label="PP-none", site=site)
        assert RoutePlannerView()._prefill_structure(cable, "A") is None

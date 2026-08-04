"""The Route tab pathway picker (issue #106).

The picker used to be a hand-rendered <select> filled from a single guessed
structure, so it silently offered nothing and TomSelect displayed "no results
found". It is now a DynamicModelChoiceField filtered by the cable end's
candidate nodes.
"""

import json

import pytest
from django.contrib.gis.geos import LineString, Point
from django.test import RequestFactory

from netbox_pathways import forms
from netbox_pathways.geo import get_srid
from netbox_pathways.models import Pathway, Structure
from netbox_pathways.views import CableRoutingAddSegmentView
from tests.conftest import build_cable_with_terminations

SRID = get_srid()


def _static_params(form):
    """The connected_to values the pathway widget will send, sorted.

    APISelect._process_query_param passes values through set(), so order is not
    preserved and comparisons must sort.
    """
    raw = form.fields["pathway"].widget.attrs.get("data-static-params")
    if not raw:
        return []
    for entry in json.loads(raw):
        if entry["queryParam"] == "connected_to":
            return sorted(entry["queryValue"])
    return []


def _get_form(admin_user, cable, **params):
    request = RequestFactory().get(f"/plugins/pathways/cable-routing/{cable.pk}/add-segment/", params)
    request.user = admin_user
    response = CableRoutingAddSegmentView.as_view()(request, cable_pk=cable.pk)
    return response


@pytest.fixture
def site(db):
    from dcim.models import Site

    return Site.objects.create(name="RP-site", slug="rp-site")


@pytest.mark.django_db
class TestRouteSegmentForm:
    def test_connected_to_reaches_the_widget(self, db):
        form = forms.RouteSegmentForm(connected_to=[("structure", 7), ("location", 3)])
        assert _static_params(form) == ["location:3", "structure:7"]

    def test_no_candidates_means_no_filter(self, db):
        assert _static_params(forms.RouteSegmentForm(connected_to=[])) == []

    def test_pathway_is_required(self, db):
        form = forms.RouteSegmentForm(data={})
        assert form.is_valid() is False
        assert "pathway" in form.errors

    def test_a_pathway_outside_the_candidate_set_still_validates(self, db):
        """POST must accept whatever the user picked, including via show-all."""
        structure = Structure.objects.create(name="RP-x", geometry=Point(0, 0, srid=SRID))
        pathway = Pathway.objects.create(
            label="RP-far",
            pathway_type="conduit",
            path=LineString((0, 0), (10, 0), srid=SRID),
            start_structure=structure,
        )
        form = forms.RouteSegmentForm(data={"pathway": pathway.pk}, connected_to=[("structure", 999999)])
        assert form.is_valid() is True


@pytest.mark.django_db
class TestAddSegmentPicker:
    def test_alphabetically_first_structure_need_not_be_on_the_pathway(self, site, admin_user):
        """#106 case C: the old code anchored to Structure.objects.first()."""
        Structure.objects.create(name="RP-aaa-unconnected", site=site, geometry=Point(0, 0, srid=SRID))
        b = Structure.objects.create(name="RP-mmm", site=site, geometry=Point(100, 0, srid=SRID))
        c = Structure.objects.create(name="RP-zzz", site=site, geometry=Point(200, 0, srid=SRID))
        Pathway.objects.create(
            label="RP-P1",
            pathway_type="conduit",
            path=LineString((100, 0), (200, 0), srid=SRID),
            start_structure=b,
            end_structure=c,
        )
        cable = build_cable_with_terminations(label="RP-cable-c", site=site)
        params = _static_params(_get_form(admin_user, cable).context_data["form"])
        assert f"structure:{b.pk}" in params

    def test_a_location_terminated_pathway_is_reachable(self, site, admin_user):
        """#106's deeper defect: the old resolver could only return structures."""
        from dcim.models import Location

        location = Location.objects.create(name="RP-room", slug="rp-room", site=site)
        structure = Structure.objects.create(name="RP-far-end", geometry=Point(0, 0, srid=SRID))
        Pathway.objects.create(
            label="RP-indoor",
            pathway_type="conduit",
            path=LineString((0, 0), (50, 0), srid=SRID),
            start_location=location,
            end_structure=structure,
        )
        cable = build_cable_with_terminations(label="RP-cable-loc", site=site, location=location)
        params = _static_params(_get_form(admin_user, cable).context_data["form"])
        assert f"location:{location.pk}" in params

    def test_unresolved_end_falls_back_to_every_pathway(self, site, admin_user):
        """#106 case A: no anchor must not mean an empty picker."""
        cable = build_cable_with_terminations(label="RP-cable-a", site=site)
        response = _get_form(admin_user, cable)
        assert _static_params(response.context_data["form"]) == []
        assert response.context_data["show_all"] is True

    def test_show_all_clears_the_filter(self, site, admin_user):
        structure = Structure.objects.create(name="RP-anchored", site=site, geometry=Point(0, 0, srid=SRID))
        Pathway.objects.create(
            label="RP-P2",
            pathway_type="conduit",
            path=LineString((0, 0), (10, 0), srid=SRID),
            start_structure=structure,
        )
        cable = build_cable_with_terminations(label="RP-cable-showall", site=site)
        assert _static_params(_get_form(admin_user, cable).context_data["form"]) != []
        assert _static_params(_get_form(admin_user, cable, show_all="1").context_data["form"]) == []

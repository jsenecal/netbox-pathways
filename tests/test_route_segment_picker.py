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


def _static_params(form, param="connected_to"):
    """The values the pathway widget will send for `param`, sorted.

    APISelect._process_query_param passes values through set(), so order is not
    preserved and comparisons must sort.
    """
    raw = form.fields["pathway"].widget.attrs.get("data-static-params")
    if not raw:
        return []
    for entry in json.loads(raw):
        if entry["queryParam"] == param:
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

    def test_cable_end_ref_reaches_the_widget_as_one_param(self, db):
        """A whole site's worth of candidates must not become a param each."""
        form = forms.RouteSegmentForm(cable_end_ref="41:A")
        assert _static_params(form, "connected_to_cable_end") == ["41:A"]
        assert _static_params(form) == []

    def test_cable_end_ref_wins_over_explicit_nodes(self, db):
        form = forms.RouteSegmentForm(cable_end_ref="41:A", connected_to=[("structure", 7)])
        assert _static_params(form, "connected_to_cable_end") == ["41:A"]
        assert _static_params(form) == []

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
    def test_first_segment_filters_by_the_cable_end_not_by_each_node(self, site, admin_user):
        """The anchor resolves server-side, so the URL stays one param long.

        A site can hold thousands of structures; one param per candidate node
        overruns nginx's header buffers and Django's field limit, which
        TomSelect shows as "no results found" -- issue #106 all over again.
        """
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
        form = _get_form(admin_user, cable).context_data["form"]
        assert _static_params(form, "connected_to_cable_end") == [f"{cable.pk}:A"]
        assert _static_params(form) == []

    def test_unresolved_end_falls_back_to_every_pathway(self, site, admin_user):
        """#106 case A: no anchor must not mean an empty picker."""
        cable = build_cable_with_terminations(label="RP-cable-a", site=site)
        response = _get_form(admin_user, cable)
        form = response.context_data["form"]
        # No filter at all -- not even the cable-end ref, which would resolve
        # to nothing and empty the dropdown.
        assert _static_params(form) == []
        assert _static_params(form, "connected_to_cable_end") == []
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
        anchored = _get_form(admin_user, cable).context_data["form"]
        assert _static_params(anchored, "connected_to_cable_end") != []
        widened = _get_form(admin_user, cable, show_all="1").context_data["form"]
        assert _static_params(widened, "connected_to_cable_end") == []
        assert _static_params(widened) == []

    def test_mid_route_offers_both_ends_of_the_previous_pathway(self, site, admin_user):
        """Pathways are drawn in either direction, so the far end is a guess.

        Offering both endpoints always includes the cable's true position; the
        old code offered `end_structure` unconditionally and so pointed behind
        the cable whenever the pathway was drawn against the run.
        """
        from netbox_pathways.models import CableSegment

        near = Structure.objects.create(name="RP-near", site=site, geometry=Point(0, 0, srid=SRID))
        far = Structure.objects.create(name="RP-far", site=site, geometry=Point(100, 0, srid=SRID))
        pathway = Pathway.objects.create(
            label="RP-P3",
            pathway_type="conduit",
            path=LineString((0, 0), (100, 0), srid=SRID),
            start_structure=near,
            end_structure=far,
        )
        cable = build_cable_with_terminations(label="RP-cable-mid", site=site)
        CableSegment.objects.create(cable=cable, pathway=pathway, sequence=1)

        form = _get_form(admin_user, cable).context_data["form"]
        assert _static_params(form) == sorted([f"structure:{near.pk}", f"structure:{far.pk}"])
        # Mid-route is not a cable end.
        assert _static_params(form, "connected_to_cable_end") == []

    def test_mid_route_junction_endpoint_is_offered(self, site, admin_user):
        """A branch conduit's junction end used to resolve to nothing.

        `_endpoint_nodes` reads junction endpoints from annotations the picker's
        queryset did not add, so both the structure and the location were null
        and the picker silently widened to every pathway at the tap.
        """
        from netbox_pathways.models import CableSegment, Conduit, ConduitJunction

        s0 = Structure.objects.create(name="RP-j0", site=site, geometry=Point(0, 0, srid=SRID))
        s1 = Structure.objects.create(name="RP-j1", site=site, geometry=Point(100, 0, srid=SRID))
        s2 = Structure.objects.create(name="RP-j2", site=site, geometry=Point(50, 50, srid=SRID))
        trunk = Conduit.objects.create(
            label="RP-trunk",
            path=LineString((0, 0), (100, 0), srid=SRID),
            start_structure=s0,
            end_structure=s1,
        )
        stub = Conduit.objects.create(
            label="RP-stub",
            path=LineString((50, 50), (50, 50), srid=SRID),
            start_structure=s2,
            end_structure=s2,
        )
        junction = ConduitJunction.objects.create(
            label="RP-J",
            trunk_conduit=trunk,
            branch_conduit=stub,
            towards_structure=s1,
            position_on_trunk=0.5,
        )
        branch = Conduit.objects.create(
            label="RP-branch",
            path=LineString((50, 0), (50, 50), srid=SRID),
            start_structure=s2,
            end_junction=junction,
        )
        cable = build_cable_with_terminations(label="RP-cable-junction", site=site)
        CableSegment.objects.create(cable=cable, pathway=branch.pathway_ptr, sequence=1)

        form = _get_form(admin_user, cable).context_data["form"]
        assert f"junction:{junction.pk}" in _static_params(form)

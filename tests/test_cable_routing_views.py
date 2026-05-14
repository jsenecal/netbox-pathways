"""Tests for cable routing panel view helpers."""

import pytest
from django.contrib.gis.geos import LineString, Point
from django.test import RequestFactory

from netbox_pathways.geo import get_srid
from netbox_pathways.models import CableSegment, Pathway, Structure
from netbox_pathways.views import CableRoutingMixin, _annotate_segments
from tests.conftest import build_cable_with_terminations

SRID = get_srid()


@pytest.fixture
def factory():
    return RequestFactory()


@pytest.fixture
def _disable_routability_signal():
    """Disconnect the pre_save routability check so we can build orphan segments.

    The CableSegment routability signal requires both A and B cable terminations
    before saving. These tests focus on view helpers and shouldn't have to wire
    full Cable + CableTermination + Device fixtures for every segment.
    """
    from django.db.models.signals import pre_save

    from netbox_pathways.signals import enforce_cable_routability

    pre_save.disconnect(enforce_cable_routability, sender=CableSegment)
    yield
    pre_save.connect(enforce_cable_routability, sender=CableSegment)


@pytest.fixture
def linear_topology(db):
    """Three structures linked by two pathways: A -- P1 -- B -- P2 -- C."""
    a = Structure.objects.create(name="A", location=Point(0, 0, srid=SRID))
    b = Structure.objects.create(name="B", location=Point(100, 0, srid=SRID))
    c = Structure.objects.create(name="C", location=Point(200, 0, srid=SRID))
    p1 = Pathway.objects.create(
        label="P1",
        pathway_type="conduit",
        path=LineString((0, 0), (100, 0), srid=SRID),
        start_structure=a,
        end_structure=b,
    )
    p2 = Pathway.objects.create(
        label="P2",
        pathway_type="conduit",
        path=LineString((100, 0), (200, 0), srid=SRID),
        start_structure=b,
        end_structure=c,
    )
    return {"a": a, "b": b, "c": c, "p1": p1, "p2": p2}


# ---------------------------------------------------------------------------
# _far_end_node
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFarEndNode:
    def test_returns_end_when_entering_from_start(self, linear_topology):
        mixin = CableRoutingMixin()
        p1 = linear_topology["p1"]
        a = linear_topology["a"]
        result = mixin._far_end_node(p1, coming_from_node=("structure", a.pk))
        assert result == ("structure", linear_topology["b"].pk)

    def test_returns_start_when_entering_from_end(self, linear_topology):
        mixin = CableRoutingMixin()
        p1 = linear_topology["p1"]
        b = linear_topology["b"]
        result = mixin._far_end_node(p1, coming_from_node=("structure", b.pk))
        assert result == ("structure", linear_topology["a"].pk)

    def test_no_coming_from_returns_end(self, linear_topology):
        # Default case: when coming_from is None, return the canonical end node.
        mixin = CableRoutingMixin()
        result = mixin._far_end_node(linear_topology["p1"])
        assert result == ("structure", linear_topology["b"].pk)


# ---------------------------------------------------------------------------
# _annotate_segments
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAnnotateSegments:
    @pytest.fixture(autouse=True)
    def _no_routability_check(self, _disable_routability_signal):
        yield

    def test_empty_list_is_no_op(self):
        segments = []
        _annotate_segments(segments)
        assert segments == []

    def test_annotates_each_segment(self, linear_topology):
        from dcim.models import Cable

        cable = Cable.objects.create()
        seg1 = CableSegment.objects.create(
            cable=cable,
            pathway=linear_topology["p1"],
            sequence=1,
        )
        seg2 = CableSegment.objects.create(
            cable=cable,
            pathway=linear_topology["p2"],
            sequence=2,
        )
        segments = [seg1, seg2]
        _annotate_segments(segments)

        # ordinal: 1-based index in the list
        assert seg1.ordinal == 1
        assert seg2.ordinal == 2

        # gap_before: True iff sequence is not exactly previous + 1; first is False
        assert seg1.gap_before is False
        assert seg2.gap_before is False
        assert seg1.prev_sequence == 0
        assert seg2.prev_sequence == 1

        # start_name / end_name come from str(pathway.start_endpoint / end_endpoint)
        assert seg1.start_name == str(linear_topology["a"])
        assert seg1.end_name == str(linear_topology["b"])
        assert seg2.start_name == str(linear_topology["b"])
        assert seg2.end_name == str(linear_topology["c"])

        # Direction inference: linear A -> B -> C means seg1 entry=A, exit=B
        a_pk = linear_topology["a"].pk
        b_pk = linear_topology["b"].pk
        c_pk = linear_topology["c"].pk
        assert seg1._entry_pk == a_pk
        assert seg1._exit_pk == b_pk
        assert seg2._entry_pk == b_pk
        assert seg2._exit_pk == c_pk

    def test_gap_before_set_when_sequence_jumps(self, linear_topology):
        from dcim.models import Cable

        cable = Cable.objects.create()
        seg1 = CableSegment.objects.create(
            cable=cable,
            pathway=linear_topology["p1"],
            sequence=1,
        )
        # Sequence jumps from 1 to 5 -- a gap
        seg2 = CableSegment.objects.create(
            cable=cable,
            pathway=linear_topology["p2"],
            sequence=5,
        )
        segments = [seg1, seg2]
        _annotate_segments(segments)

        assert seg1.gap_before is False
        assert seg2.gap_before is True
        # gap_start_pk / gap_end_pk wire the "Plan Route for this gap" button
        assert seg2.gap_start_pk == seg1._exit_pk
        assert seg2.gap_end_pk == seg2._entry_pk

    def test_segment_without_pathway_has_no_endpoint_names(self, linear_topology):
        from dcim.models import Cable

        cable = Cable.objects.create()
        # Segment with pathway=None (dangling / placeholder)
        orphan = CableSegment.objects.create(cable=cable, pathway=None, sequence=1)
        _annotate_segments([orphan])
        assert orphan.start_name is None
        assert orphan.end_name is None
        assert orphan.ordinal == 1


# ---------------------------------------------------------------------------
# _start_node / _end_node
# ---------------------------------------------------------------------------


@pytest.fixture
def site(db):
    from dcim.models import Site

    return Site.objects.create(name="CR-site", slug="cr-site")


@pytest.fixture
def site_structure(site):
    return Structure.objects.create(
        name="CR-struct",
        site=site,
        location=Point(0, 0, srid=SRID),
    )


@pytest.mark.django_db
class TestStartEndNode:
    def test_returns_none_when_no_termination(self):
        from dcim.models import Cable

        mixin = CableRoutingMixin()
        cable = Cable.objects.create(label="no-term")
        assert mixin._start_node(cable) is None
        assert mixin._end_node(cable) is None

    def test_start_node_resolves_single_structure(self, site, site_structure):
        mixin = CableRoutingMixin()
        cable = build_cable_with_terminations(
            label="CR-A",
            site=site,
            terminate_a=True,
            terminate_b=False,
        )
        assert mixin._start_node(cable) == ("structure", site_structure.pk)
        # B side has no termination -> None
        assert mixin._end_node(cable) is None

    def test_end_node_resolves_single_structure(self, site, site_structure):
        mixin = CableRoutingMixin()
        cable = build_cable_with_terminations(
            label="CR-B",
            site=site,
            terminate_a=False,
            terminate_b=True,
        )
        assert mixin._end_node(cable) == ("structure", site_structure.pk)
        assert mixin._start_node(cable) is None

    def test_start_node_picks_first_when_multiple_structures(self, site):
        # Two structures in the same site: the mixin falls back to first()
        s1 = Structure.objects.create(
            name="CR-multi-1",
            site=site,
            location=Point(0, 0, srid=SRID),
        )
        s2 = Structure.objects.create(
            name="CR-multi-2",
            site=site,
            location=Point(10, 10, srid=SRID),
        )
        mixin = CableRoutingMixin()
        cable = build_cable_with_terminations(
            label="CR-multi",
            site=site,
            terminate_a=True,
            terminate_b=False,
        )
        result = mixin._start_node(cable)
        # Either structure can win first(); pin to one of the two known PKs.
        assert result is not None
        kind, pk = result
        assert kind == "structure"
        assert pk in {s1.pk, s2.pk}


# ---------------------------------------------------------------------------
# _render_table
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRenderTable:
    @pytest.fixture(autouse=True)
    def _no_routability_check(self, _disable_routability_signal):
        yield

    def test_renders_segments_with_labels(self, factory, admin_user, linear_topology):
        from dcim.models import Cable

        cable = Cable.objects.create(label="CR-render")
        CableSegment.objects.create(
            cable=cable,
            pathway=linear_topology["p1"],
            sequence=1,
        )

        request = factory.get(f"/pathways/cable/{cable.pk}/routing/table/")
        request.user = admin_user

        mixin = CableRoutingMixin()
        response = mixin._render_table(request, cable)
        assert response.status_code == 200
        # The pathway label appears in the rendered table fragment
        assert b"P1" in response.content

    def test_renders_empty_state_when_no_segments(self, factory, admin_user):
        from dcim.models import Cable

        cable = Cable.objects.create(label="CR-empty")
        request = factory.get(f"/pathways/cable/{cable.pk}/routing/table/")
        request.user = admin_user

        mixin = CableRoutingMixin()
        response = mixin._render_table(request, cable)
        assert response.status_code == 200
        # The template renders an empty-state message rather than the table
        assert b"No segments in this cable" in response.content


# ---------------------------------------------------------------------------
# CableRoutingAddSegmentView.post
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAddSegmentPost:
    @pytest.fixture(autouse=True)
    def _no_routability_check(self, _disable_routability_signal):
        yield

    def test_creates_first_segment_with_sequence_one(self, factory, admin_user, linear_topology):
        from dcim.models import Cable

        from netbox_pathways.views import CableRoutingAddSegmentView

        cable = Cable.objects.create(label="CR-add-first")
        p1 = linear_topology["p1"]
        request = factory.post(
            f"/pathways/cable/{cable.pk}/routing/add/",
            data={"pathway": str(p1.pk)},
        )
        request.user = admin_user

        response = CableRoutingAddSegmentView().post(request, cable_pk=cable.pk)
        assert response.status_code == 200

        segments = list(CableSegment.objects.filter(cable=cable).order_by("sequence"))
        assert len(segments) == 1
        assert segments[0].sequence == 1
        assert segments[0].pathway_id == p1.pk

    def test_after_sequence_inserts_and_shifts_later_segments(self, factory, admin_user, linear_topology):
        from dcim.models import Cable

        from netbox_pathways.views import CableRoutingAddSegmentView

        cable = Cable.objects.create(label="CR-add-shift")
        p1 = linear_topology["p1"]
        p2 = linear_topology["p2"]

        # Seed two segments at sequences 1 and 2
        seg1 = CableSegment.objects.create(cable=cable, pathway=p1, sequence=1)
        seg2 = CableSegment.objects.create(cable=cable, pathway=p2, sequence=2)

        request = factory.post(
            f"/pathways/cable/{cable.pk}/routing/add/",
            data={"pathway": str(p1.pk), "after_sequence": "1"},
        )
        request.user = admin_user

        response = CableRoutingAddSegmentView().post(request, cable_pk=cable.pk)
        assert response.status_code == 200

        segments = list(CableSegment.objects.filter(cable=cable).order_by("sequence"))
        assert len(segments) == 3
        # seg1 still at sequence 1
        seg1.refresh_from_db()
        assert seg1.sequence == 1
        # new segment inserted at sequence 2 with pathway p1
        assert segments[1].sequence == 2
        assert segments[1].pathway_id == p1.pk
        assert segments[1].pk not in (seg1.pk, seg2.pk)
        # previously-at-2 segment shifted to 3
        seg2.refresh_from_db()
        assert seg2.sequence == 3


# ---------------------------------------------------------------------------
# CableRoutingDeleteSegmentView.post
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDeleteSegmentPost:
    @pytest.fixture(autouse=True)
    def _no_routability_check(self, _disable_routability_signal):
        yield

    def test_deletes_specified_segment_and_returns_table(self, factory, admin_user, linear_topology):
        from dcim.models import Cable

        from netbox_pathways.views import CableRoutingDeleteSegmentView

        cable = Cable.objects.create(label="CR-del")
        seg = CableSegment.objects.create(
            cable=cable,
            pathway=linear_topology["p1"],
            sequence=1,
        )

        request = factory.post(f"/pathways/cable/{cable.pk}/routing/delete/{seg.pk}/")
        request.user = admin_user

        response = CableRoutingDeleteSegmentView().post(request, cable_pk=cable.pk, segment_pk=seg.pk)
        assert response.status_code == 200
        assert not CableSegment.objects.filter(pk=seg.pk).exists()


# ---------------------------------------------------------------------------
# CableRoutingApplyRouteView.post
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestApplyRoutePost:
    @pytest.fixture(autouse=True)
    def _no_routability_check(self, _disable_routability_signal):
        yield

    def test_replaces_existing_segments_with_pathway_ids(self, factory, admin_user, linear_topology):
        from dcim.models import Cable

        from netbox_pathways.views import CableRoutingApplyRouteView

        cable = Cable.objects.create(label="CR-apply")
        p1 = linear_topology["p1"]
        p2 = linear_topology["p2"]

        # Pre-existing segment at p2 only
        CableSegment.objects.create(cable=cable, pathway=p2, sequence=1)

        request = factory.post(
            f"/pathways/cable/{cable.pk}/routing/apply/",
            data={"pathway_ids": f"{p1.pk},{p2.pk}"},
        )
        request.user = admin_user

        response = CableRoutingApplyRouteView().post(request, cable_pk=cable.pk)
        assert response.status_code == 200

        segments = list(CableSegment.objects.filter(cable=cable).order_by("sequence"))
        assert [s.sequence for s in segments] == [1, 2]
        assert [s.pathway_id for s in segments] == [p1.pk, p2.pk]

    def test_empty_pathway_ids_clears_all_segments(self, factory, admin_user, linear_topology):
        from dcim.models import Cable

        from netbox_pathways.views import CableRoutingApplyRouteView

        cable = Cable.objects.create(label="CR-apply-empty")
        CableSegment.objects.create(
            cable=cable,
            pathway=linear_topology["p1"],
            sequence=1,
        )

        request = factory.post(
            f"/pathways/cable/{cable.pk}/routing/apply/",
            data={"pathway_ids": ""},
        )
        request.user = admin_user

        response = CableRoutingApplyRouteView().post(request, cable_pk=cable.pk)
        assert response.status_code == 200
        assert CableSegment.objects.filter(cable=cable).count() == 0

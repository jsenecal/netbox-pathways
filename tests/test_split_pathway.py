"""Tests for the pathway split service module.

Regression suite for issue #87: split one long imported polyline into
per-hop pathways between the structures it passes.
"""

import pytest
from dcim.models import Site
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.geo import get_srid
from netbox_pathways.models import (
    AerialSpan,
    Conduit,
    ConduitBank,
    ConduitJunction,
    Innerduct,
    Pathway,
    PathwayLocation,
    PlannedRoute,
    Structure,
)
from netbox_pathways.split import SplitError, _cut_line, find_candidates, plan_split

SRID = get_srid()


def _structure(name, x, y):
    return Structure.objects.create(name=name, geometry=Point(x, y, srid=SRID))


def _span(start, end, path, **kwargs):
    return AerialSpan.objects.create(
        path=path,
        start_structure=start,
        end_structure=end,
        **kwargs,
    )


@pytest.mark.django_db
class TestFindCandidates:
    def test_orders_by_chainage_excludes_endpoints_and_out_of_tolerance(self):
        start = _structure("FC-A", 0, 0)
        end = _structure("FC-B", 300, 0)
        near_far_along = _structure("FC-mid2", 200, 0.5)
        near_early = _structure("FC-mid1", 100, -0.4)
        _structure("FC-off", 150, 50)  # 50 units off the line: not a candidate
        span = _span(start, end, LineString((0, 0), (300, 0), srid=SRID))

        candidates = find_candidates(span, tolerance=1.0)

        assert [c.structure.pk for c in candidates] == [near_early.pk, near_far_along.pk]
        assert candidates[0].chainage == pytest.approx(100.0)
        assert candidates[0].offset == pytest.approx(0.4)
        assert candidates[1].chainage == pytest.approx(200.0)

    def test_pathway_without_path_raises(self):
        span = AerialSpan(path=None)
        with pytest.raises(SplitError, match="path"):
            find_candidates(span, tolerance=1.0)


class TestCutLine:
    """Pure-geometry tests; no DB needed."""

    def test_vertices_land_in_the_right_children(self):
        line = LineString((0, 0), (100, 0), (200, 0), (300, 0), (400, 0), (500, 0), srid=SRID)
        cuts = [
            (150.0, Point(150, 0, srid=SRID)),
            (350.0, Point(350, 0, srid=SRID)),
        ]
        pieces = _cut_line(line, cuts)
        assert [tuple(p.coords) for p in pieces] == [
            ((0.0, 0.0), (100.0, 0.0), (150.0, 0.0)),
            ((150.0, 0.0), (200.0, 0.0), (300.0, 0.0), (350.0, 0.0)),
            ((350.0, 0.0), (400.0, 0.0), (500.0, 0.0)),
        ]

    def test_cut_on_existing_vertex_replaces_it(self):
        line = LineString((0, 0), (100, 0), (200, 0), srid=SRID)
        # Structure sits 0.3 off the drawn vertex; the vertex is replaced by
        # the structure point, not duplicated (no zero-length segment).
        pieces = _cut_line(line, [(100.0, Point(100, 0.3, srid=SRID))])
        assert [tuple(p.coords) for p in pieces] == [
            ((0.0, 0.0), (100.0, 0.3)),
            ((100.0, 0.3), (200.0, 0.0)),
        ]

    def test_offline_cut_point_is_written_verbatim(self):
        line = LineString((0, 0), (300, 0), srid=SRID)
        pieces = _cut_line(line, [(150.0, Point(150, 0.4, srid=SRID))])
        assert tuple(pieces[0].coords) == ((0.0, 0.0), (150.0, 0.4))
        assert tuple(pieces[1].coords) == ((150.0, 0.4), (300.0, 0.0))

    def test_two_cuts_in_the_same_segment(self):
        line = LineString((0, 0), (300, 0), srid=SRID)
        pieces = _cut_line(line, [(100.0, Point(100, 0, srid=SRID)), (200.0, Point(200, 0, srid=SRID))])
        assert [tuple(p.coords) for p in pieces] == [
            ((0.0, 0.0), (100.0, 0.0)),
            ((100.0, 0.0), (200.0, 0.0)),
            ((200.0, 0.0), (300.0, 0.0)),
        ]

    def test_srid_preserved(self):
        line = LineString((0, 0), (300, 0), srid=SRID)
        pieces = _cut_line(line, [(150.0, Point(150, 0, srid=SRID))])
        assert all(p.srid == SRID for p in pieces)

    def test_cut_at_line_start_raises(self):
        line = LineString((0, 0), (100, 0), srid=SRID)
        with pytest.raises(ValueError, match="interior"):
            _cut_line(line, [(0.0, Point(0, 0, srid=SRID))])

    def test_cut_at_line_end_raises(self):
        line = LineString((0, 0), (100, 0), srid=SRID)
        with pytest.raises(ValueError, match="interior"):
            _cut_line(line, [(100.0, Point(100, 0, srid=SRID))])


@pytest.mark.django_db
class TestPlanSplit:
    def _line_span(self, prefix, length=300):
        start = _structure(f"{prefix}-A", 0, 0)
        end = _structure(f"{prefix}-B", length, 0)
        span = _span(start, end, LineString((0, 0), (length, 0), srid=SRID))
        return span, start, end

    def test_orders_cuts_and_resolves_concrete_subclass(self):
        span, _, _ = self._line_span("PS1")
        s2 = _structure("PS1-m2", 200, 0)
        s1 = _structure("PS1-m1", 100, 0)
        base = Pathway.objects.get(pk=span.pk)  # command fetches the base row

        plan = plan_split(base, [s2, s1], tolerance=1.0)

        assert isinstance(plan.pathway, AerialSpan)
        assert [c.structure.pk for c in plan.cuts] == [s1.pk, s2.pk]
        assert plan.warnings == []

    def test_structure_beyond_tolerance_refused(self):
        span, _, _ = self._line_span("PS2")
        off = _structure("PS2-off", 150, 30)
        with pytest.raises(SplitError, match="tolerance"):
            plan_split(span, [off], tolerance=1.0)

    def test_structure_at_line_end_skipped_with_warning(self):
        span, _, _ = self._line_span("PS3")
        at_end = _structure("PS3-end", 300, 0.5)
        mid = _structure("PS3-mid", 150, 0)
        plan = plan_split(span, [at_end, mid], tolerance=1.0)
        assert [c.structure.pk for c in plan.cuts] == [mid.pk]
        assert any("end" in w for w in plan.warnings)

    def test_coincident_structures_collapse_with_warning(self):
        span, _, _ = self._line_span("PS4")
        s1 = _structure("PS4-s1", 150, 0.2)
        s2 = _structure("PS4-s2", 150, -0.2)  # same chainage
        plan = plan_split(span, [s1, s2], tolerance=1.0)
        assert len(plan.cuts) == 1
        assert any("collaps" in w for w in plan.warnings)

    def test_no_usable_structures_refused(self):
        span, _, _ = self._line_span("PS5")
        with pytest.raises(SplitError, match="[Nn]o usable"):
            plan_split(span, [], tolerance=1.0)

    def test_indoor_pathway_refused(self):
        pw = Pathway(path=None)
        with pytest.raises(SplitError, match="path"):
            plan_split(pw, [], tolerance=1.0)

    def test_innerduct_refused(self):
        s1 = _structure("PS6-A", 0, 0)
        s2 = _structure("PS6-B", 100, 0)
        conduit = Conduit.objects.create(
            path=LineString((0, 0), (100, 0), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )
        duct = Innerduct.objects.create(parent_conduit=conduit, size="32mm")
        with pytest.raises(SplitError, match="[Ii]nnerduct"):
            plan_split(duct, [], tolerance=1.0)

    def test_bank_contained_conduit_refused(self):
        s1 = _structure("PS7-A", 0, 0)
        s2 = _structure("PS7-B", 100, 0)
        bank = ConduitBank.objects.create(
            path=LineString((0, 0), (100, 0), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )
        conduit = Conduit.objects.create(conduit_bank=bank)
        with pytest.raises(SplitError, match="bank"):
            plan_split(conduit, [], tolerance=1.0)

    def test_conduit_with_junction_refused(self):
        s1 = _structure("PS8-A", 0, 0)
        s2 = _structure("PS8-B", 300, 0)
        trunk = Conduit.objects.create(
            path=LineString((0, 0), (300, 0), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )
        s3 = _structure("PS8-C", 150, 100)
        branch = Conduit.objects.create(
            path=LineString((150, 0), (150, 100), srid=SRID),
            end_structure=s3,
        )
        junction = ConduitJunction(
            trunk_conduit=trunk,
            branch_conduit=branch,
            towards_structure=s2,
            position_on_trunk=0.5,
        )
        junction.save()
        branch.start_junction = junction
        branch.save()
        mid = _structure("PS8-mid", 100, 0)
        with pytest.raises(SplitError, match="junction"):
            plan_split(trunk, [mid], tolerance=1.0)
        with pytest.raises(SplitError, match="junction"):
            plan_split(branch, [], tolerance=1.0)

    def test_waypoints_and_planned_routes_produce_warnings(self):
        span, _, _ = self._line_span("PS9")
        mid = _structure("PS9-mid", 150, 0)
        site = Site.objects.create(name="PS9-site", slug="ps9-site")
        PathwayLocation.objects.create(pathway=span, site=site, sequence=1)
        route = PlannedRoute.objects.create(
            name="PS9-route",
            start_structure=span.start_structure,
            end_structure=span.end_structure,
            pathway_ids=[span.pk],
        )
        plan = plan_split(span, [mid], tolerance=1.0)
        assert any("waypoint" in w for w in plan.warnings)
        assert any(route.name in w for w in plan.warnings)

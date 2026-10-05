"""reanchor_pathways: find and repair pathway ends left behind by bulk writes."""

from io import StringIO

import pytest
from django.contrib.gis.geos import LineString, Point
from django.core.management import call_command

from netbox_pathways.models import AerialSpan, Pathway, Structure
from tests.helpers import SRID, coords, make_aerial_span, make_building, make_conduit, make_pole


def _bulk_move(structure, x, y):
    """Move a structure the way a bulk write does: without save()."""
    Structure.objects.filter(pk=structure.pk).update(geometry=Point(x, y, srid=SRID))


def _run(*args):
    out = StringIO()
    call_command("reanchor_pathways", *args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
class TestReanchorPathwaysCommand:
    def test_dry_run_reports_drift_and_writes_nothing(self):
        s1, s2 = make_pole("S1", 0, 0), make_pole("S2", 100, 0)
        conduit = make_conduit([(0, 0), (50, 20), (100, 0)], start_structure=s1, end_structure=s2)
        _bulk_move(s2, 100, 30)

        output = _run()

        assert f"pk {conduit.pk}" in output
        assert "end vertex is 30.00 from its anchor" in output
        assert coords(conduit, refresh=True)[-1] == (100.0, 0.0)

    def test_apply_moves_drifted_ends_and_straightens_bent_spans(self):
        s1, s2 = make_pole("S1", 0, 0), make_pole("S2", 100, 0)
        conduit = make_conduit([(0, 0), (50, 20), (100, 0)], start_structure=s1, end_structure=s2)
        p1, p2 = make_pole("P1", 0, 50), make_pole("P2", 40, 50)
        span = make_aerial_span(p1, p2)
        Pathway.objects.filter(pk=span.pk).update(path=LineString((0, 50), (20, 60), (40, 50), srid=SRID))
        _bulk_move(s2, 100, 30)

        _run("--apply")

        assert coords(conduit, refresh=True) == [(0.0, 0.0), (50.0, 20.0), (100.0, 30.0)]
        assert coords(span, refresh=True) == [(0.0, 50.0), (40.0, 50.0)]

    def test_detached_span_is_reported_and_left_alone(self):
        p1 = make_pole("P1", 0, 0)
        span = AerialSpan(start_structure=p1, path=LineString((0, 0), (30, 0), srid=SRID))
        span.save()

        before = Pathway.objects.get(pk=span.pk).last_updated

        output = _run("--apply")

        assert "end vertex is not attached to a structure" in output
        assert "Repaired 0 pathway(s); 1 need(s) attention" in output
        assert Pathway.objects.get(pk=span.pk).last_updated == before

    def test_scan_query_count_does_not_grow_with_pathways(self, django_assert_max_num_queries):
        poles = [make_pole(f"Q{i}", i * 100, 0) for i in range(7)]
        for a, b in zip(poles, poles[1:], strict=False):
            make_conduit([(a.geometry.x, 0), (b.geometry.x, 0)], start_structure=a, end_structure=b)
            make_aerial_span(a, b)

        with django_assert_max_num_queries(20):
            _run()

    def test_end_inside_a_footprint_counts_as_attached(self):
        """Drift uses the same attachment rule as clean(): inside a footprint is attached."""
        building = make_building("B1", 0, 0)
        pole = make_pole("P1", 60, 5)
        make_conduit([(10, 5), (60, 5)], start_structure=building, end_structure=pole)
        Pathway.objects.update(path=LineString((5, 5), (60, 5), srid=SRID))

        assert "All pathway ends sit on their anchors." in _run()

    def test_unknown_structure_pk_is_rejected(self):
        from django.core.management.base import CommandError

        with pytest.raises(CommandError, match=r"Structure PK\(s\) not found: \[999999\]"):
            _run("--structure", "999999")

    def test_structure_filter_limits_the_scan(self):
        a1, a2 = make_pole("A1", 0, 0), make_pole("A2", 100, 0)
        b1, b2 = make_pole("B1", 0, 500), make_pole("B2", 100, 500)
        kept = make_conduit([(0, 0), (100, 0)], start_structure=a1, end_structure=a2)
        skipped = make_conduit([(0, 500), (100, 500)], start_structure=b1, end_structure=b2)
        _bulk_move(a2, 100, 10)
        _bulk_move(b2, 100, 510)

        output = _run("--structure", str(a2.pk))

        assert f"pk {kept.pk}" in output
        assert f"pk {skipped.pk}" not in output

"""reanchor_pathways: find and repair pathway ends left behind by bulk writes."""

from io import StringIO

import pytest
from django.contrib.gis.geos import LineString, Point
from django.core.management import call_command

from netbox_pathways.geo import get_srid
from netbox_pathways.models import AerialSpan, Conduit, Pathway, Structure

SRID = get_srid()


def _pole(name, x, y):
    return Structure.objects.create(name=name, geometry=Point(x, y, srid=SRID))


def _bulk_move(structure, x, y):
    """Move a structure the way a bulk write does: without save()."""
    Structure.objects.filter(pk=structure.pk).update(geometry=Point(x, y, srid=SRID))


def _conduit(start, end, path):
    conduit = Conduit(start_structure=start, end_structure=end, path=LineString(path, srid=SRID))
    conduit.save()
    return conduit


def _run(*args):
    out = StringIO()
    call_command("reanchor_pathways", *args, stdout=out)
    return out.getvalue()


def _coords(pathway):
    path = Pathway.objects.get(pk=pathway.pk).path
    return [(round(x, 6), round(y, 6)) for x, y in path.coords]


@pytest.mark.django_db
class TestReanchorPathwaysCommand:
    def test_dry_run_reports_drift_and_writes_nothing(self):
        s1, s2 = _pole("S1", 0, 0), _pole("S2", 100, 0)
        conduit = _conduit(s1, s2, [(0, 0), (50, 20), (100, 0)])
        _bulk_move(s2, 100, 30)

        output = _run()

        assert f"pk {conduit.pk}" in output
        assert "end vertex is 30.00 from its anchor" in output
        assert _coords(conduit)[-1] == (100.0, 0.0)

    def test_apply_moves_drifted_ends_and_straightens_bent_spans(self):
        s1, s2 = _pole("S1", 0, 0), _pole("S2", 100, 0)
        conduit = _conduit(s1, s2, [(0, 0), (50, 20), (100, 0)])
        p1, p2 = _pole("P1", 0, 50), _pole("P2", 40, 50)
        span = AerialSpan(start_structure=p1, end_structure=p2)
        span.full_clean()
        span.save()
        Pathway.objects.filter(pk=span.pk).update(path=LineString((0, 50), (20, 60), (40, 50), srid=SRID))
        _bulk_move(s2, 100, 30)

        _run("--apply")

        assert _coords(conduit) == [(0.0, 0.0), (50.0, 20.0), (100.0, 30.0)]
        assert _coords(span) == [(0.0, 50.0), (40.0, 50.0)]

    def test_detached_span_is_reported_and_left_alone(self):
        p1 = _pole("P1", 0, 0)
        span = AerialSpan(start_structure=p1, path=LineString((0, 0), (30, 0), srid=SRID))
        span.save()

        before = Pathway.objects.get(pk=span.pk).last_updated

        output = _run("--apply")

        assert "end vertex is not attached to a structure" in output
        assert "Repaired 0 pathway(s); 1 need(s) attention" in output
        assert Pathway.objects.get(pk=span.pk).last_updated == before

    def test_scan_query_count_does_not_grow_with_pathways(self, django_assert_max_num_queries):
        poles = [_pole(f"Q{i}", i * 100, 0) for i in range(7)]
        for a, b in zip(poles, poles[1:], strict=False):
            _conduit(a, b, [(a.geometry.x, 0), (b.geometry.x, 0)])
            span = AerialSpan(start_structure=a, end_structure=b)
            span.full_clean()
            span.save()

        with django_assert_max_num_queries(20):
            _run()

    def test_structure_filter_limits_the_scan(self):
        a1, a2 = _pole("A1", 0, 0), _pole("A2", 100, 0)
        b1, b2 = _pole("B1", 0, 500), _pole("B2", 100, 500)
        kept = _conduit(a1, a2, [(0, 0), (100, 0)])
        skipped = _conduit(b1, b2, [(0, 500), (100, 500)])
        _bulk_move(a2, 100, 10)
        _bulk_move(b2, 100, 510)

        output = _run("--structure", str(a2.pk))

        assert f"pk {kept.pk}" in output
        assert f"pk {skipped.pk}" not in output

"""Tests for `Pathway.geo_length` -- PostGIS-side ST_Length computation.

These tests deliberately prove that the length is computed by PostGIS in SQL,
not in Python. A naive `self.path.length` implementation would still pass
"value matches" assertions because GeoDjango's LineString carries a Python-side
length too -- so the contract is verified by inspecting the SQL that's
emitted, not just the numeric value.
"""

import pytest
from django.contrib.gis.geos import LineString, Point
from django.db import connection
from django.test.utils import CaptureQueriesContext

from netbox_pathways.geo import get_srid
from netbox_pathways.models import (
    AerialSpan,
    Conduit,
    ConduitBank,
    DirectBuried,
    Innerduct,
    Pathway,
    Structure,
)


@pytest.fixture
def srid():
    return get_srid()


@pytest.fixture
def structures(db, srid):
    return [
        Structure.objects.create(
            name=f"GL-S{i}",
            location=Point(i * 1000.0, 0.0, srid=srid),
            structure_type="manhole",
        )
        for i in range(3)
    ]


@pytest.fixture
def conduit(structures, srid):
    return Conduit.objects.create(
        label="GL-C1",
        start_structure=structures[0],
        end_structure=structures[1],
        path=LineString((0.0, 0.0), (1000.0, 0.0), srid=srid),
    )


@pytest.mark.django_db
class TestWithGeoLengthAnnotation:
    """`PathwayQuerySet.with_geo_length()` adds a PostGIS-computed length."""

    def test_annotated_queryset_sql_calls_st_length(self, conduit):
        """The annotation must translate to ST_Length(...) in the emitted SQL."""
        with CaptureQueriesContext(connection) as ctx:
            list(Pathway.objects.with_geo_length().values("pk", "_geo_length"))
        sql_joined = " ".join(q["sql"] for q in ctx.captured_queries).upper()
        assert "ST_LENGTH(" in sql_joined, (
            "with_geo_length() must compute length via PostGIS ST_Length; "
            f"emitted SQL did not contain ST_Length: {sql_joined}"
        )

    def test_annotated_value_uses_field_name_geo_length(self, conduit):
        """Annotation must expose the value under `_geo_length` for property fallback."""
        qs = Pathway.objects.with_geo_length()
        instance = qs.get(pk=conduit.pk)
        assert hasattr(instance, "_geo_length"), (
            "with_geo_length() must annotate as `_geo_length` so the property "
            "can detect when the queryset already carries the value"
        )


@pytest.mark.django_db
class TestGeoLengthProperty:
    """`Pathway.geo_length` property contract: annotated vs fallback."""

    def test_property_uses_annotation_without_extra_query(self, conduit):
        """When `_geo_length` is annotated, the property must reuse it (no extra SQL)."""
        instance = Pathway.objects.with_geo_length().get(pk=conduit.pk)
        with CaptureQueriesContext(connection) as ctx:
            value = instance.geo_length
        assert value is not None
        # No additional queries: annotated value is reused, not recomputed.
        assert len(ctx.captured_queries) == 0, (
            "geo_length must reuse the `_geo_length` annotation when present; "
            f"unexpected extra queries: {[q['sql'] for q in ctx.captured_queries]}"
        )

    def test_property_fallback_emits_st_length_sql(self, conduit):
        """Without annotation, property access must issue a PostGIS ST_Length query."""
        instance = Pathway.objects.get(pk=conduit.pk)
        assert not hasattr(instance, "_geo_length") or instance.__dict__.get("_geo_length") is None
        with CaptureQueriesContext(connection) as ctx:
            value = instance.geo_length
        assert value is not None
        sql_joined = " ".join(q["sql"] for q in ctx.captured_queries).upper()
        assert "ST_LENGTH(" in sql_joined, (
            "geo_length fallback must compute via PostGIS ST_Length, not via "
            f"Python LineString.length; emitted SQL: {sql_joined}"
        )

    def test_property_returns_metres_for_projected_srid(self, conduit):
        """For a 1000 m LineString in the configured projected SRID, geo_length ~= 1000.

        This is a sanity check on units, not a test of PostGIS correctness;
        the SQL-emission tests above prove that PostGIS is doing the work.
        """
        instance = Pathway.objects.with_geo_length().get(pk=conduit.pk)
        assert instance.geo_length == pytest.approx(1000.0, rel=1e-3)


@pytest.mark.django_db
class TestGeoLengthRounding:
    """`geo_length` is a display value: survey-grade GPS is centimetre-scale
    at best, so the property rounds to 2 decimals (centimetres) by default,
    overridable via `PLUGINS_CONFIG['netbox_pathways']['geo_length_decimals']`
    (0 = whole metres). Refs #80.
    """

    @pytest.fixture
    def diagonal_conduit(self, structures, srid):
        # sqrt(1000^2 + 1000^2) = 1414.2135623730951 m
        return Conduit.objects.create(
            label="GL-diag",
            start_structure=structures[0],
            end_structure=structures[1],
            path=LineString((0.0, 0.0), (1000.0, 1000.0), srid=srid),
        )

    def test_default_rounds_to_centimetres(self, diagonal_conduit):
        instance = Pathway.objects.with_geo_length().get(pk=diagonal_conduit.pk)
        assert instance.geo_length == pytest.approx(1414.21)

    def test_fallback_path_also_rounds(self, diagonal_conduit):
        instance = Pathway.objects.get(pk=diagonal_conduit.pk)
        assert instance.geo_length == pytest.approx(1414.21)

    def test_zero_decimals_rounds_to_whole_metres(self, diagonal_conduit, settings):
        settings.PLUGINS_CONFIG["netbox_pathways"]["geo_length_decimals"] = 0
        try:
            instance = Pathway.objects.with_geo_length().get(pk=diagonal_conduit.pk)
            assert instance.geo_length == 1414
        finally:
            del settings.PLUGINS_CONFIG["netbox_pathways"]["geo_length_decimals"]


@pytest.mark.django_db
class TestGeoLengthFilterSet:
    """`PathwayFilterSet.geo_length__gte` / `__lte` must filter via PostGIS,
    not Python, even when the list view's queryset already paid for the
    annotation. The proof: the emitted SQL must filter on `ST_Length(...)`.
    """

    def _make_conduit(self, structures, srid, label, length_m):
        return Conduit.objects.create(
            label=label,
            start_structure=structures[0],
            end_structure=structures[1],
            path=LineString((0.0, 0.0), (length_m, 0.0), srid=srid),
        )

    def test_filter_gte_emits_st_length_sql(self, structures, srid):
        from netbox_pathways.filters import PathwayFilterSet

        self._make_conduit(structures, srid, "short", 100.0)
        self._make_conduit(structures, srid, "long", 5000.0)
        qs = Pathway.objects.with_geo_length()
        fs = PathwayFilterSet({"geo_length__gte": "1000"}, queryset=qs)
        with CaptureQueriesContext(connection) as ctx:
            list(fs.qs.values_list("pk", flat=True))
        sql_joined = " ".join(q["sql"] for q in ctx.captured_queries).upper()
        assert "ST_LENGTH(" in sql_joined, (
            f"geo_length__gte must filter via PostGIS ST_Length; emitted SQL did not call ST_Length: {sql_joined}"
        )

    def test_filter_gte_returns_only_matching_rows(self, structures, srid):
        from netbox_pathways.filters import PathwayFilterSet

        self._make_conduit(structures, srid, "short", 100.0)
        long_pw = self._make_conduit(structures, srid, "long", 5000.0)
        qs = Pathway.objects.with_geo_length()
        fs = PathwayFilterSet({"geo_length__gte": "1000"}, queryset=qs)
        labels = list(fs.qs.values_list("label", flat=True))
        assert labels == [long_pw.label]


@pytest.mark.django_db
@pytest.mark.parametrize("model_cls", [Conduit, AerialSpan, DirectBuried, Innerduct, ConduitBank])
class TestSubclassManagerInheritsWithGeoLength:
    """`with_geo_length()` must be available on every concrete Pathway subclass,
    so list views and external callers can annotate without dropping to the
    base `Pathway.objects`. This is what lets PostGIS-side sorting work in the
    subclass-specific list views.
    """

    def test_subclass_manager_exposes_with_geo_length(self, db, model_cls):
        assert hasattr(model_cls.objects, "with_geo_length"), (
            f"{model_cls.__name__}.objects must expose with_geo_length() so "
            "list views and filters can annotate at the DB level"
        )

    def test_subclass_annotation_emits_st_length(self, db, model_cls):
        with CaptureQueriesContext(connection) as ctx:
            list(model_cls.objects.with_geo_length().values("pk", "_geo_length"))
        sql_joined = " ".join(q["sql"] for q in ctx.captured_queries).upper()
        assert "ST_LENGTH(" in sql_joined, (
            f"{model_cls.__name__}.objects.with_geo_length() must compute via "
            f"PostGIS ST_Length; emitted SQL: {sql_joined}"
        )

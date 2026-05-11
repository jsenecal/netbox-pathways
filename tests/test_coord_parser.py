"""
Tests for the Python coordinate parser used by bulk-import forms.

parse_geometry_input accepts the same forgiving free-text formats as the
JavaScript parser used by the interactive map widget (see issue #32):

    - GeoJSON Geometry / Feature / FeatureCollection (first feature wins)
    - WKT (POINT / LINESTRING / POLYGON), case-insensitive
    - DMS with N/S/E/W hemispheres (point only)
    - DMS without hemispheres in lat-first order (point only)
    - Bare decimal "lat, lon" pairs in Google Maps order (point only)

Coordinates are normalized to EPSG:4326.
"""

import pytest
from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ValidationError

from netbox_pathways.coord_parser import parse_geometry_input


def coords(geom):
    """Helper: return the geometry's coordinates as a (lon, lat) tuple or list."""
    if geom.geom_type == "Point":
        return (geom.x, geom.y)
    return list(geom.coords)


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------


def test_empty_string_returns_none():
    assert parse_geometry_input("") is None


def test_whitespace_only_returns_none():
    assert parse_geometry_input("   \n\t  ") is None


def test_none_input_returns_none():
    assert parse_geometry_input(None) is None


# ---------------------------------------------------------------------------
# GeoJSON
# ---------------------------------------------------------------------------


def test_geojson_point_passthrough():
    geom = parse_geometry_input('{"type":"Point","coordinates":[-73.5,45.5]}')
    assert geom.geom_type == "Point"
    assert geom.srid == 4326
    assert (geom.x, geom.y) == pytest.approx((-73.5, 45.5))


def test_geojson_linestring_passthrough():
    geom = parse_geometry_input('{"type":"LineString","coordinates":[[-73.5,45.5],[-73.4,45.6]]}')
    assert geom.geom_type == "LineString"
    assert geom.srid == 4326


def test_geojson_feature_unwrapped():
    text = '{"type":"Feature","properties":{},"geometry":{"type":"Point","coordinates":[-73.5,45.5]}}'
    geom = parse_geometry_input(text)
    assert geom.geom_type == "Point"
    assert (geom.x, geom.y) == pytest.approx((-73.5, 45.5))


def test_geojson_featurecollection_first_feature_wins():
    text = (
        '{"type":"FeatureCollection","features":['
        '{"type":"Feature","properties":{},"geometry":{"type":"Point","coordinates":[-73.5,45.5]}},'
        '{"type":"Feature","properties":{},"geometry":{"type":"Point","coordinates":[0,0]}}'
        "]}"
    )
    geom = parse_geometry_input(text)
    assert (geom.x, geom.y) == pytest.approx((-73.5, 45.5))


def test_geojson_feature_with_null_geometry_rejected():
    text = '{"type":"Feature","properties":{},"geometry":null}'
    with pytest.raises(ValidationError, match=r"(?i)no geometry"):
        parse_geometry_input(text)


# ---------------------------------------------------------------------------
# WKT
# ---------------------------------------------------------------------------


def test_wkt_point():
    geom = parse_geometry_input("POINT(-73.5 45.5)")
    assert geom.geom_type == "Point"
    assert (geom.x, geom.y) == pytest.approx((-73.5, 45.5))


def test_wkt_linestring():
    geom = parse_geometry_input("LINESTRING(-73.5 45.5, -73.4 45.6, -73.3 45.7)")
    assert geom.geom_type == "LineString"
    assert len(geom.coords) == 3


def test_wkt_lowercase_with_whitespace():
    geom = parse_geometry_input("  point ( -73.5   45.5 )  ")
    assert geom.geom_type == "Point"


# ---------------------------------------------------------------------------
# DMS with hemispheres
# ---------------------------------------------------------------------------


def test_dms_with_hemispheres():
    geom = parse_geometry_input("45 30 15 N 73 34 00 W")
    assert geom.geom_type == "Point"
    assert geom.y == pytest.approx(45.5041667, rel=1e-5)
    assert geom.x == pytest.approx(-73.5666667, rel=1e-5)


def test_dms_with_symbols_and_hemispheres():
    geom = parse_geometry_input("45d30'15\"N 73d34'00\"W")
    assert geom.geom_type == "Point"
    assert geom.y == pytest.approx(45.5041667, rel=1e-5)
    assert geom.x == pytest.approx(-73.5666667, rel=1e-5)


def test_dms_with_comma_separator():
    geom = parse_geometry_input("45 30 15 N, 73 34 00 W")
    assert geom.geom_type == "Point"


# ---------------------------------------------------------------------------
# DMS without hemispheres (lat-first by convention)
# ---------------------------------------------------------------------------


def test_dms_without_hemispheres_lat_first():
    geom = parse_geometry_input("45 30 15 -73 34 00")
    assert geom.geom_type == "Point"
    assert geom.y == pytest.approx(45.5041667, rel=1e-5)
    assert geom.x == pytest.approx(-73.5666667, rel=1e-5)


# ---------------------------------------------------------------------------
# Bare decimal "lat, lon" (Google Maps order)
# ---------------------------------------------------------------------------


def test_decimal_comma_separated():
    geom = parse_geometry_input("41.40338, 2.17403")
    assert geom.geom_type == "Point"
    assert geom.y == pytest.approx(41.40338)
    assert geom.x == pytest.approx(2.17403)


def test_decimal_space_separated():
    geom = parse_geometry_input("45.5 -73.5")
    assert geom.geom_type == "Point"
    assert geom.y == pytest.approx(45.5)
    assert geom.x == pytest.approx(-73.5)


def test_decimal_negative_pair():
    geom = parse_geometry_input("-45.5,-73.5")
    assert geom.geom_type == "Point"
    assert geom.y == pytest.approx(-45.5)
    assert geom.x == pytest.approx(-73.5)


# ---------------------------------------------------------------------------
# Coordinate range validation
# ---------------------------------------------------------------------------


def test_latitude_out_of_range():
    with pytest.raises(ValidationError, match=r"(?i)latitude"):
        parse_geometry_input("91, 0")


def test_longitude_out_of_range():
    with pytest.raises(ValidationError, match=r"(?i)longitude"):
        parse_geometry_input('{"type":"Point","coordinates":[181,0]}')


def test_boundary_values_accepted():
    geom = parse_geometry_input('{"type":"Point","coordinates":[180,90]}')
    assert geom.geom_type == "Point"


# ---------------------------------------------------------------------------
# geom_type matching
# ---------------------------------------------------------------------------


def test_point_rejected_when_linestring_expected():
    with pytest.raises(ValidationError, match=r"(?i)line ?string"):
        parse_geometry_input("45.5, -73.5", geom_type="LineString")


def test_linestring_rejected_when_point_expected():
    with pytest.raises(ValidationError, match=r"(?i)point"):
        parse_geometry_input(
            '{"type":"LineString","coordinates":[[-73.5,45.5],[-73.4,45.6]]}',
            geom_type="Point",
        )


def test_any_geometry_when_no_type_constraint():
    point = parse_geometry_input('{"type":"Point","coordinates":[-73.5,45.5]}')
    assert point.geom_type == "Point"
    line = parse_geometry_input('{"type":"LineString","coordinates":[[-73.5,45.5],[-73.4,45.6]]}')
    assert line.geom_type == "LineString"


def test_geom_type_linestring_normalized_from_uppercase():
    geom = parse_geometry_input(
        '{"type":"LineString","coordinates":[[-73.5,45.5],[-73.4,45.6]]}',
        geom_type="LINESTRING",
    )
    assert geom.geom_type == "LineString"


# ---------------------------------------------------------------------------
# Malformed input
# ---------------------------------------------------------------------------


def test_gibberish_rejected():
    with pytest.raises(ValidationError):
        parse_geometry_input("this is not geometry")


def test_invalid_json_rejected():
    with pytest.raises(ValidationError):
        parse_geometry_input('{"type":"Point","coordinates":[1,')


def test_unsupported_geometry_type_rejected():
    with pytest.raises(ValidationError, match=r"(?i)unsupported|multipoint"):
        parse_geometry_input('{"type":"MultiPoint","coordinates":[[-73.5,45.5],[-73.4,45.6]]}')


# ---------------------------------------------------------------------------
# SRID
# ---------------------------------------------------------------------------


def test_always_returns_srid_4326():
    """Parser produces 4326 geometry regardless of input format."""
    cases = [
        '{"type":"Point","coordinates":[-73.5,45.5]}',
        "POINT(-73.5 45.5)",
        "45 30 15 N 73 34 00 W",
        "45.5, -73.5",
    ]
    for text in cases:
        geom = parse_geometry_input(text)
        assert geom.srid == 4326, f"input {text!r} produced srid={geom.srid}"


def test_returns_geos_geometry_instance():
    geom = parse_geometry_input("POINT(-73.5 45.5)")
    assert isinstance(geom, GEOSGeometry)


# ---------------------------------------------------------------------------
# ForgivingGeometryField (form field wrapper used by import forms)
# ---------------------------------------------------------------------------


def test_forgiving_field_reprojects_to_storage_srid():
    """clean() runs the parser AND reprojects to the field's storage SRID."""
    from netbox_pathways.coord_parser import ForgivingGeometryField

    field = ForgivingGeometryField(geom_type="POINT", srid=3348)
    geom = field.clean("45.5, -73.5")
    assert geom.geom_type == "Point"
    assert geom.srid == 3348
    # 45.5 N / 73.5 W is around Montreal -- in NAD83/Canada Atlas Lambert
    # coordinates this is roughly x=2_200_000, y=730_000 (well outside the
    # WGS84 [-180,180]/[-90,90] envelope, proving the reprojection ran).
    assert abs(geom.x) > 1_000_000
    assert abs(geom.y) > 1_000


def test_forgiving_field_empty_input_returns_none():
    from netbox_pathways.coord_parser import ForgivingGeometryField

    field = ForgivingGeometryField(geom_type="POINT", srid=4326, required=False)
    assert field.clean("") is None


def test_forgiving_field_type_mismatch_raises():
    from netbox_pathways.coord_parser import ForgivingGeometryField

    field = ForgivingGeometryField(geom_type="LINESTRING", srid=4326)
    with pytest.raises(ValidationError):
        field.clean("POINT(-73.5 45.5)")

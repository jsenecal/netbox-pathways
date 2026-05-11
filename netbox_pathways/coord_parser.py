"""
Forgiving free-text coordinate parser for bulk-import forms.

Mirrors the TypeScript parser used by the interactive map widget
(`static/.../src/coord-parser.ts`) so that CSV imports accept the same
human-friendly formats users encounter in the Coordinates tab. All
output geometries are normalized to EPSG:4326; callers reproject to
the storage SRID through the standard Django GIS save path.

Supported input formats:
    - GeoJSON Geometry / Feature / FeatureCollection (first feature wins)
    - WKT (POINT / LINESTRING / POLYGON)
    - DMS with N/S/E/W hemispheres (point only)
    - DMS without hemispheres in lat-first order (point only)
    - Bare decimal "lat, lon" pairs in Google Maps order (point only)

See issue #32.
"""

from __future__ import annotations

import json
import re

from django.contrib.gis import forms as gis_forms
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.geos.error import GEOSException
from django.core.exceptions import ValidationError

_OUTPUT_SRID = 4326
_SUPPORTED_TYPES = {"Point", "LineString", "Polygon"}

_WKT_RE = re.compile(r"^\s*(point|linestring|polygon)\s*\(", re.IGNORECASE)
_DMS_WITH_HEMI_RE = re.compile(r"\d[°dD'\"ms\s:]*[NSEWnsew]")
_NUMERIC_SPLIT_RE = re.compile(r"[°'\"dDmMsS:,\s]+")
_DMS_TOKEN_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)[°dD\s:]+(\d+(?:\.\d+)?)"
    r"(?:['m\s:]+(\d+(?:\.\d+)?))?[\"s\s]*([NSEWnsew])"
)


def parse_geometry_input(text, geom_type=None):
    """
    Parse free-text geometry input into a `GEOSGeometry` with SRID 4326.

    Returns None for empty / whitespace-only input.
    Raises `django.core.exceptions.ValidationError` for any non-empty input
    that cannot be coerced into a Point / LineString / Polygon, or whose
    type does not match the requested `geom_type`.

    `geom_type` is the expected geometry type. Accepts case-insensitive
    "Point", "LineString", "Polygon", or "Geometry" (any). None means any.
    """
    if text is None:
        return None
    stripped = text.strip() if isinstance(text, str) else None
    if not stripped:
        return None

    expected = _normalize_geom_type(geom_type)

    geom = _dispatch(stripped)
    _validate_geometry(geom)
    _check_type(geom, expected)
    return geom


def _normalize_geom_type(geom_type):
    if geom_type is None:
        return "Geometry"
    stripped = re.sub(r"\s+", "", str(geom_type)).lower()
    if stripped == "point":
        return "Point"
    if stripped == "linestring":
        return "LineString"
    if stripped == "polygon":
        return "Polygon"
    return "Geometry"


def _dispatch(text):
    first = text[0]
    if first in "{[":
        return _from_json(text)
    if _WKT_RE.match(text):
        return _from_wkt(text)
    if _DMS_WITH_HEMI_RE.search(text):
        return _from_dms_with_hemispheres(text)
    return _from_numeric_tokens(text)


def _from_json(text):
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as err:
        raise ValidationError(f"Invalid JSON: {err.msg}.") from err
    return _extract_geometry(parsed)


def _extract_geometry(obj):
    if not isinstance(obj, dict):
        raise ValidationError("JSON value is not an object.")
    obj_type = obj.get("type")
    if not isinstance(obj_type, str):
        raise ValidationError('JSON object is missing a "type" field.')

    if obj_type == "Feature":
        geometry = obj.get("geometry")
        if geometry is None:
            raise ValidationError("Feature has no geometry.")
        return _extract_geometry(geometry)
    if obj_type == "FeatureCollection":
        features = obj.get("features") or []
        if not features:
            raise ValidationError("FeatureCollection has no features.")
        first = features[0]
        if not isinstance(first, dict):
            raise ValidationError("FeatureCollection feature is malformed.")
        return _extract_geometry(first.get("geometry"))
    if obj_type in _SUPPORTED_TYPES:
        return _geos_from_json(obj)
    raise ValidationError(f'Unsupported geometry type "{obj_type}".')


def _geos_from_json(geometry_dict):
    try:
        return GEOSGeometry(json.dumps(geometry_dict), srid=_OUTPUT_SRID)
    except (GEOSException, ValueError) as err:
        raise ValidationError(f"Invalid GeoJSON geometry: {err}.") from err


def _from_wkt(text):
    try:
        geom = GEOSGeometry(text, srid=_OUTPUT_SRID)
    except (GEOSException, ValueError) as err:
        raise ValidationError(f"Invalid WKT: {err}.") from err
    if geom.geom_type not in _SUPPORTED_TYPES:
        raise ValidationError(f'Unsupported WKT geometry type "{geom.geom_type}".')
    return geom


def _from_dms_with_hemispheres(text):
    tokens = []
    for match in _DMS_TOKEN_RE.finditer(text):
        deg, minute, second, hemi = match.groups()
        tokens.append((float(deg), float(minute), float(second or 0), hemi.upper()))
    if len(tokens) != 2:
        raise ValidationError('Could not parse DMS pair. Expected "DD MM SS N/S DD MM SS E/W".')
    lat = lon = None
    for deg, minute, second, hemi in tokens:
        sign = -1 if hemi in ("S", "W") else 1
        decimal = sign * (abs(deg) + minute / 60.0 + second / 3600.0)
        if hemi in ("N", "S"):
            lat = decimal
        else:
            lon = decimal
    if lat is None or lon is None:
        raise ValidationError("DMS pair must include one N/S and one E/W hemisphere.")
    return GEOSGeometry(f"POINT({lon} {lat})", srid=_OUTPUT_SRID)


def _from_numeric_tokens(text):
    parts = [t for t in _NUMERIC_SPLIT_RE.split(text) if t and re.match(r"^-?\d", t)]
    if len(parts) == 2:
        return _point_from_decimal_pair(parts[0], parts[1])
    if len(parts) == 6:
        return _point_from_dms_triples(parts)
    raise ValidationError("Unrecognized input. Accepted formats: GeoJSON, WKT, DMS, decimal lat,lon.")


def _point_from_decimal_pair(lat_raw, lon_raw):
    try:
        lat = float(lat_raw)
        lon = float(lon_raw)
    except ValueError as err:
        raise ValidationError("Latitude and longitude must be numbers.") from err
    return GEOSGeometry(f"POINT({lon} {lat})", srid=_OUTPUT_SRID)


def _point_from_dms_triples(parts):
    try:
        nums = [float(p) for p in parts]
    except ValueError as err:
        raise ValidationError("Invalid DMS components.") from err
    lat = _dms_to_decimal(nums[0], nums[1], nums[2])
    lon = _dms_to_decimal(nums[3], nums[4], nums[5])
    return GEOSGeometry(f"POINT({lon} {lat})", srid=_OUTPUT_SRID)


def _dms_to_decimal(deg, minute, second):
    sign = -1 if deg < 0 else 1
    return sign * (abs(deg) + minute / 60.0 + second / 3600.0)


def _validate_geometry(geom):
    if geom.geom_type == "Point":
        _check_point(geom.x, geom.y)
    elif geom.geom_type == "LineString":
        for x, y in geom.coords:
            _check_point(x, y)
    elif geom.geom_type == "Polygon":
        for ring in geom.coords:
            for x, y in ring:
                _check_point(x, y)


def _check_point(lon, lat):
    if not (-180 <= lon <= 180):
        raise ValidationError(f"Longitude {lon} out of range [-180, 180].")
    if not (-90 <= lat <= 90):
        raise ValidationError(f"Latitude {lat} out of range [-90, 90].")


def _check_type(geom, expected):
    if expected == "Geometry":
        return
    if geom.geom_type != expected:
        raise ValidationError(f"Expected {expected}, got {geom.geom_type}.")


class ForgivingGeometryField(gis_forms.GeometryField):
    """
    Form field that runs free-text input through `parse_geometry_input` before
    deferring to Django's standard GeometryField for SRID reprojection and
    geom_type validation. Used by CSV import forms.
    """

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if not isinstance(value, GEOSGeometry):
            parsed = parse_geometry_input(value)
            if parsed is None:
                return None
            value = parsed
        return super().to_python(value)

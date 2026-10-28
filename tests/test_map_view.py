"""Tests for MapView — kiosk param, URL params, parse_box, safe casts, data extent."""

import re

import pytest
from django.contrib.gis.geos import Point, Polygon

from netbox_pathways.geo import get_srid
from netbox_pathways.models import Structure
from netbox_pathways.views import MapView

from .request_helpers import parse_json_script, render_map


@pytest.fixture
def view():
    return MapView()


# ---------------------------------------------------------------------------
# _parse_box
# ---------------------------------------------------------------------------


class TestParseBox:
    def test_valid_box(self):
        result = MapView._parse_box("BOX(-73.6 45.4,-73.5 45.6)")
        assert result == (-73.6, 45.4, -73.5, 45.6)

    def test_negative_coords(self):
        result = MapView._parse_box("BOX(-180 -90,180 90)")
        assert result == (-180.0, -90.0, 180.0, 90.0)

    def test_invalid_string(self):
        assert MapView._parse_box("not a box") is None

    def test_empty_string(self):
        assert MapView._parse_box("") is None

    def test_none(self):
        assert MapView._parse_box(None) is None

    def test_partial_box(self):
        assert MapView._parse_box("BOX(-73.6 45.4)") is None


# ---------------------------------------------------------------------------
# _safe_float / _safe_int
# ---------------------------------------------------------------------------


class TestSafeCasts:
    def test_safe_float_valid(self, view):
        assert view._safe_float("45.5", 0.0) == 45.5

    def test_safe_float_none(self, view):
        assert view._safe_float(None, 99.0) == 99.0

    def test_safe_float_garbage(self, view):
        assert view._safe_float("abc", 1.0) == 1.0

    def test_safe_float_int_string(self, view):
        assert view._safe_float("10", 0.0) == 10.0

    def test_safe_int_valid(self, view):
        assert view._safe_int("12", 5) == 12

    def test_safe_int_none(self, view):
        assert view._safe_int(None, 5) == 5

    def test_safe_int_garbage(self, view):
        assert view._safe_int("xyz", 7) == 7

    def test_safe_int_float_string(self, view):
        # float strings are not valid ints
        assert view._safe_int("3.5", 1) == 1


# ---------------------------------------------------------------------------
# _data_extent
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDataExtent:
    @staticmethod
    def _structure_at(name, lon, lat):
        location = Point(lon, lat, srid=4326)
        location.transform(get_srid())
        return Structure.objects.create(name=name, geometry=location, structure_type="manhole")

    def test_outlier_structures_trimmed(self):
        """Structures more than 2 degrees from the cluster's mean position are
        excluded from the initial extent, so one bad GPS fix cannot zoom the
        whole map out."""
        for i in range(5):
            self._structure_at(f"Extent-Cluster-{i}", -73.6 + i * 0.01, 45.5)
        self._structure_at("Extent-Outlier", -78.6, 45.5)

        west, south, east, north = MapView()._data_extent()

        assert west >= -74  # outlier at -78.6 trimmed away
        assert east <= -73
        assert 45 <= south <= north <= 46

    def test_polygon_footprint_structure(self):
        """Regression for #71: ST_Y() only accepts points, so a structure with
        a polygon footprint must not break the trimmed-extent query."""
        srid = get_srid()
        Structure.objects.create(
            name="Extent-Point",
            geometry=Point(100, 100, srid=srid),
            structure_type="manhole",
        )
        Structure.objects.create(
            name="Extent-Footprint",
            geometry=Polygon(((0, 0), (50, 0), (50, 50), (0, 50), (0, 0)), srid=srid),
            structure_type="vault",
        )

        extent = MapView()._data_extent()

        assert extent is not None
        west, south, east, north = extent
        # The footprint's full extent (not just its centroid) must be covered:
        # its (0, 0) corner is the bbox's southwest, the point its northeast.
        origin = Point(0, 0, srid=srid)
        origin.transform(4326)
        assert west <= origin.x
        assert south <= origin.y
        assert east > west
        assert north > south


# ---------------------------------------------------------------------------
# MapView.get — kiosk and URL params
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMapViewGet:
    """Test the MapView.get() method with various query parameters."""

    def _wrapper_classes(self, content):
        """Classes on the map wrapper div.

        Matched as a set rather than a literal substring: the CSS rules in the
        page mention the same class names, and the wrapper carries more than
        one of them in kiosk mode.
        """
        match = re.search(r'class="(pathways-map-wrapper[^"]*)"', content)
        return set(match.group(1).split()) if match else set()

    def test_kiosk_true(self):
        content = render_map("kiosk=true")
        classes = self._wrapper_classes(content)
        # pw-maximized is the shared full-viewport box; pw-kiosk adds the
        # map-page specifics on top of it.
        assert "pw-kiosk" in classes
        assert "pw-maximized" in classes

    def test_kiosk_false(self):
        content = render_map("kiosk=false")
        assert "pw-kiosk" not in self._wrapper_classes(content)

    def test_kiosk_missing(self):
        content = render_map("")
        assert "pw-kiosk" not in self._wrapper_classes(content)

    def test_kiosk_case_insensitive(self):
        content = render_map("kiosk=TRUE")
        assert "pw-kiosk" in self._wrapper_classes(content)

    def test_config_carries_status_choices(self):
        """The inactive-set panel must not depend on an /info round-trip
        (skipped entirely at high zoom), so statuses ship with the page."""
        content = render_map("")
        assert '"statuses"' in content
        assert '"retired"' in content

    def test_invalid_lat_uses_default(self):
        content = render_map("lat=notanumber&lon=2.3")


# ---------------------------------------------------------------------------
# MapView.get — client config payload
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMapConfigPayload:
    """The client config must survive any active locale and honour the
    documented precedence: lat/lon params > ?select= > data extent > defaults.
    """

    def test_center_is_json_not_localized(self, settings):
        """Regression for #93: under a locale that formats decimals with a
        comma, template interpolation rendered `center: [52,42, 10,78]` --
        four array items -- and Leaflet threw on `t.lat`. The config must be
        serialized as JSON, which is locale-independent.
        """
        from django.utils import translation

        settings.PLUGINS_CONFIG = {
            **settings.PLUGINS_CONFIG,
            "netbox_pathways": {
                **settings.PLUGINS_CONFIG.get("netbox_pathways", {}),
                "map_center_lat": 52.42,
                "map_center_lon": 10.78,
            },
        }

        with translation.override("de"):
            content = render_map()

        assert parse_json_script(content, "pathways-map-init")["center"] == [52.42, 10.78]
        # No comma-formatted decimal may reach the page at all.
        assert "52,42" not in content

    def test_lat_lon_params_win_over_data_extent(self):
        """An explicit viewport must not be overridden by the data extent:
        `bounds` would otherwise reach Leaflet and fitBounds beats setView.
        """
        content = render_map(
            "lat=48.8&lon=2.3&zoom=15",
            extent=(-73.6, 45.4, -73.5, 45.6),
        )

        config = parse_json_script(content, "pathways-map-init")
        assert config["center"] == [48.8, 2.3]
        assert config["zoom"] == 15
        assert config["bounds"] is None

    def test_lat_lon_without_zoom_falls_back_to_configured_zoom(self, settings):
        settings.PLUGINS_CONFIG = {
            **settings.PLUGINS_CONFIG,
            "netbox_pathways": {
                **settings.PLUGINS_CONFIG.get("netbox_pathways", {}),
                "map_zoom": 12,
            },
        }

        content = render_map("lat=48.8&lon=2.3")

        assert parse_json_script(content, "pathways-map-init")["zoom"] == 12

    def test_selected_feature_reaches_client(self):
        """The sidebar auto-opens the selected feature from this value."""
        content = render_map(
            "select=structure-123",
            feature_extent=(-73.6, 45.4, -73.5, 45.6),
        )

        config = parse_json_script(content, "pathways-map-init")
        assert config["select"] == "structure-123"
        assert config["bounds"] == [[45.4, -73.6], [45.6, -73.5]]
        # Close zoom for a single feature, used only if fitBounds is skipped.
        assert config["zoom"] == 18

    def test_selected_feature_bounds_win_over_data_extent(self):
        content = render_map(
            "select=structure-123",
            extent=(-10.0, -10.0, 10.0, 10.0),
            feature_extent=(-73.6, 45.4, -73.5, 45.6),
        )

        assert parse_json_script(content, "pathways-map-init")["bounds"] == [
            [45.4, -73.6],
            [45.6, -73.5],
        ]

    def test_unresolvable_selection_falls_back_to_data_extent(self):
        content = render_map(
            "select=structure-999",
            extent=(-73.6, 45.4, -73.5, 45.6),
            feature_extent=None,
        )

        assert parse_json_script(content, "pathways-map-init")["bounds"] == [
            [45.4, -73.6],
            [45.6, -73.5],
        ]

    def test_data_extent_used_when_no_params(self):
        content = render_map(extent=(-73.6, 45.4, -73.5, 45.6))

        config = parse_json_script(content, "pathways-map-init")
        assert config["center"] == [45.5, -73.55]
        assert config["bounds"] == [[45.4, -73.6], [45.6, -73.5]]

    def test_kiosk_flag_in_config(self):
        assert parse_json_script(render_map("kiosk=true"), "pathways-map-init")["kiosk"] is True
        assert parse_json_script(render_map(), "pathways-map-init")["kiosk"] is False

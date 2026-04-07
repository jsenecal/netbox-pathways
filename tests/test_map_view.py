"""Tests for MapView — kiosk param, URL params, parse_box, safe casts."""

import json
from unittest.mock import patch

import pytest
from django.test import RequestFactory

from netbox_pathways.views import MapView


@pytest.fixture
def factory():
    return RequestFactory()


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
# MapView.get — kiosk and URL params
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMapViewGet:
    """Test the MapView.get() method with various query parameters.

    Patches _data_extent to avoid DB hits and isolate param logic.
    """

    def _get(self, factory, query_string=""):
        request = factory.get(f"/plugins/pathways/map/?{query_string}")
        # LoginRequiredMixin needs request.user
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()
        view = MapView()
        with patch.object(view, '_data_extent', return_value=None):
            # Bypass LoginRequiredMixin — call get() directly after dispatch
            response = view.get(request)
        return response

    def test_kiosk_true(self, factory):
        response = self._get(factory, "kiosk=true")
        assert response.status_code == 200
        content = response.content.decode()
        # The wrapper div should have the pw-kiosk class
        assert 'pathways-map-wrapper pw-kiosk' in content

    def test_kiosk_false(self, factory):
        response = self._get(factory, "kiosk=false")
        assert response.status_code == 200
        content = response.content.decode()
        # Wrapper div should NOT have pw-kiosk class (CSS rules still mention it)
        assert 'pathways-map-wrapper pw-kiosk' not in content

    def test_kiosk_missing(self, factory):
        response = self._get(factory, "")
        assert response.status_code == 200
        content = response.content.decode()
        assert 'pathways-map-wrapper pw-kiosk' not in content

    def test_kiosk_case_insensitive(self, factory):
        response = self._get(factory, "kiosk=TRUE")
        content = response.content.decode()
        assert 'pathways-map-wrapper pw-kiosk' in content

    def test_lat_lon_zoom_params(self, factory):
        response = self._get(factory, "lat=48.8&lon=2.3&zoom=15")
        content = response.content.decode()
        assert '48.8' in content
        assert '2.3' in content
        assert '15' in content

    def test_lat_lon_without_zoom_uses_default(self, factory):
        response = self._get(factory, "lat=48.8&lon=2.3")
        assert response.status_code == 200

    def test_kiosk_js_config(self, factory):
        """The JS init config should contain kiosk: true when param is set."""
        response = self._get(factory, "kiosk=true")
        content = response.content.decode()
        assert 'kiosk: true' in content

    def test_no_kiosk_js_config(self, factory):
        """The JS init config should contain kiosk: false when param is not set."""
        response = self._get(factory, "")
        content = response.content.decode()
        assert 'kiosk: false' in content

    def test_invalid_lat_uses_default(self, factory):
        response = self._get(factory, "lat=notanumber&lon=2.3")
        assert response.status_code == 200

    def test_extent_used_when_no_params(self, factory):
        """When no lat/lon params, _data_extent result is used."""
        request = factory.get("/plugins/pathways/map/")
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()
        view = MapView()
        extent = (-73.6, 45.4, -73.5, 45.6)
        with patch.object(view, '_data_extent', return_value=extent):
            response = view.get(request)
        content = response.content.decode()
        # Center should be midpoint of extent
        expected_lat = (45.4 + 45.6) / 2
        assert str(expected_lat) in content

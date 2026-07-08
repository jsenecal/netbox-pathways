"""Tests for the GeoJSON API endpoints and the geo utility module."""

import pytest
from dcim.models import Site
from django.contrib.gis.geos import LineString, Point
from rest_framework.test import APIClient

from netbox_pathways.geo import (
    LEAFLET_SRID,
    get_srid,
    linestring_to_coords,
    point_to_latlon,
    point_to_lonlat,
    to_leaflet,
)
from netbox_pathways.models import AerialSpan, Conduit, ConduitBank, DirectBuried, Structure

# ---------------------------------------------------------------------------
# geo.py utility functions
# ---------------------------------------------------------------------------


class TestGeoUtilities:
    def test_get_srid_returns_int(self):
        srid = get_srid()
        assert isinstance(srid, int)
        assert srid > 0

    def test_to_leaflet_none(self):
        assert to_leaflet(None) is None

    def test_to_leaflet_transforms(self):
        srid = get_srid()
        pt = Point(100, 200, srid=srid)
        result = to_leaflet(pt)
        assert result.srid == LEAFLET_SRID

    def test_to_leaflet_preserves_original(self):
        srid = get_srid()
        pt = Point(100, 200, srid=srid)
        to_leaflet(pt)
        assert pt.srid == srid  # original unchanged

    def test_point_to_lonlat_none(self):
        assert point_to_lonlat(None) is None

    def test_point_to_lonlat_returns_tuple(self):
        srid = get_srid()
        pt = Point(100, 200, srid=srid)
        result = point_to_lonlat(pt)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_point_to_latlon_none(self):
        assert point_to_latlon(None) is None

    def test_point_to_latlon_swaps_lonlat(self):
        srid = get_srid()
        pt = Point(100, 200, srid=srid)
        lonlat = point_to_lonlat(pt)
        latlon = point_to_latlon(pt)
        assert latlon == (lonlat[1], lonlat[0])

    def test_linestring_to_coords_none(self):
        assert linestring_to_coords(None) == []

    def test_linestring_to_coords_returns_list(self):
        srid = get_srid()
        line = LineString((100, 200), (300, 400), srid=srid)
        result = linestring_to_coords(line)
        assert isinstance(result, list)
        assert len(result) == 2
        # Each coord is [lon, lat]
        assert len(result[0]) == 2


# ---------------------------------------------------------------------------
# GeoJSON API — fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def srid():
    return get_srid()


@pytest.fixture
def site():
    return Site.objects.create(name="GeoAPI Test Site", slug="geoapi-test")


@pytest.fixture
def structures(srid, site):
    return [
        Structure.objects.create(
            name=f"Geo-S{i}",
            location=Point(i * 100, i * 100, srid=srid),
            site=site,
            structure_type="manhole",
        )
        for i in range(1, 4)
    ]


@pytest.fixture
def conduits(structures, srid):
    return [
        Conduit.objects.create(
            label=f"Geo-C{i}",
            start_structure=structures[i],
            end_structure=structures[i + 1],
            path=LineString(
                (i * 100, i * 100),
                ((i + 1) * 100, (i + 1) * 100),
                srid=srid,
            ),
            length=100,
        )
        for i in range(2)
    ]


@pytest.fixture
def aerial_span(structures, srid):
    return AerialSpan.objects.create(
        label="Geo-A1",
        start_structure=structures[0],
        end_structure=structures[1],
        path=LineString((100, 100), (200, 200), srid=srid),
        length=50,
    )


@pytest.fixture
def direct_buried(structures, srid):
    return DirectBuried.objects.create(
        label="Geo-DB1",
        start_structure=structures[1],
        end_structure=structures[2],
        path=LineString((200, 200), (300, 300), srid=srid),
        length=75,
    )


@pytest.fixture
def conduit_bank(structures, srid):
    return ConduitBank.objects.create(
        label="Geo-CB1",
        start_structure=structures[0],
        end_structure=structures[2],
        path=LineString((100, 100), (300, 300), srid=srid),
        length=200,
    )


@pytest.fixture
def api_client():
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    user = user_model.objects.create_user(username="geotest", password="geotest", is_superuser=True)  # noqa: S106
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ---------------------------------------------------------------------------
# GeoJSON API — Structure endpoint
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStructureGeoAPI:
    def test_list_returns_geojson(self, api_client, structures):
        resp = api_client.get("/api/plugins/pathways/geo/structures/", format="json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) >= 3

    def test_features_have_geometry(self, api_client, structures):
        resp = api_client.get("/api/plugins/pathways/geo/structures/", format="json")
        data = resp.json()
        for feat in data["features"]:
            assert feat["geometry"] is not None
            assert feat["geometry"]["type"] == "Point"
            assert "coordinates" in feat["geometry"]
            lon, lat = feat["geometry"]["coordinates"]
            # Transformed to WGS84 — coordinates should be in valid range
            assert -180 <= lon <= 180
            assert -90 <= lat <= 90

    def test_features_have_properties(self, api_client, structures):
        resp = api_client.get("/api/plugins/pathways/geo/structures/", format="json")
        data = resp.json()
        props = data["features"][0]["properties"]
        assert "name" in props
        assert "structure_type" in props

    def test_etag_header(self, api_client, structures):
        resp = api_client.get("/api/plugins/pathways/geo/structures/", format="json")
        assert "ETag" in resp

    def test_etag_304_on_second_request(self, api_client, structures):
        resp1 = api_client.get("/api/plugins/pathways/geo/structures/", format="json")
        etag = resp1["ETag"]
        resp2 = api_client.get(
            "/api/plugins/pathways/geo/structures/",
            format="json",
            HTTP_IF_NONE_MATCH=etag,
        )
        assert resp2.status_code == 304

    def test_bbox_filter(self, api_client, structures):
        # Get one structure's WGS84 coords, build tight bbox
        resp = api_client.get("/api/plugins/pathways/geo/structures/", format="json")
        data = resp.json()
        if data["features"]:
            feat = data["features"][0]
            lon, lat = feat["geometry"]["coordinates"]
            bbox = f"{lon - 0.01},{lat - 0.01},{lon + 0.01},{lat + 0.01}"
            resp2 = api_client.get(
                f"/api/plugins/pathways/geo/structures/?bbox={bbox}",
                format="json",
            )
            assert resp2.status_code == 200
            # Should return at least the one structure within bbox
            assert len(resp2.json()["features"]) >= 1

    def test_bbox_filter_excludes_far_features(self, api_client, structures):
        # Use a bbox far from any structures
        resp = api_client.get(
            "/api/plugins/pathways/geo/structures/?bbox=170,80,171,81",
            format="json",
        )
        assert resp.status_code == 200
        assert len(resp.json()["features"]) == 0

    def test_zoom_param_accepted(self, api_client, structures):
        resp = api_client.get("/api/plugins/pathways/geo/structures/?zoom=10", format="json")
        assert resp.status_code == 200

    def test_invalid_bbox_ignored(self, api_client, structures):
        resp = api_client.get(
            "/api/plugins/pathways/geo/structures/?bbox=invalid",
            format="json",
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GeoJSON API — Pathway endpoint (conduits, aerial, direct buried, banks)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPathwayGeoAPI:
    def test_pathway_list(self, api_client, conduits):
        resp = api_client.get("/api/plugins/pathways/geo/pathways/", format="json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"

    def test_pathway_geometry_is_linestring(self, api_client, conduits):
        resp = api_client.get("/api/plugins/pathways/geo/pathways/", format="json")
        data = resp.json()
        for feat in data["features"]:
            if feat["geometry"]:
                assert feat["geometry"]["type"] == "LineString"

    def test_conduit_geo(self, api_client, conduits):
        resp = api_client.get("/api/plugins/pathways/geo/conduits/", format="json")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["features"]) >= 2

    def test_aerial_span_geo(self, api_client, aerial_span):
        resp = api_client.get("/api/plugins/pathways/geo/aerial-spans/", format="json")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["features"]) >= 1

    def test_direct_buried_geo(self, api_client, direct_buried):
        resp = api_client.get("/api/plugins/pathways/geo/direct-buried/", format="json")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["features"]) >= 1

    def test_conduit_bank_geo(self, api_client, conduit_bank):
        resp = api_client.get("/api/plugins/pathways/geo/conduit-banks/", format="json")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["features"]) >= 1

    def test_pathway_etag(self, api_client, conduits):
        resp1 = api_client.get("/api/plugins/pathways/geo/pathways/", format="json")
        etag = resp1.get("ETag")
        assert etag
        resp2 = api_client.get(
            "/api/plugins/pathways/geo/pathways/",
            format="json",
            HTTP_IF_NONE_MATCH=etag,
        )
        assert resp2.status_code == 304


# ---------------------------------------------------------------------------
# GeoJSON API — exclude_status (issue #68: hide inactive infrastructure)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExcludeStatus:
    def test_structures_exclude_status(self, api_client, structures):
        retired = structures[0]
        retired.status = "retired"
        retired.save()
        resp = api_client.get(
            "/api/plugins/pathways/geo/structures/?exclude_status=retired",
            format="json",
        )
        assert resp.status_code == 200
        ids = [f["id"] for f in resp.json()["features"]]
        assert retired.pk not in ids
        assert len(ids) == len(structures) - 1

    def test_conduits_exclude_multiple_statuses(self, api_client, conduits):
        conduits[0].status = "retired"
        conduits[0].save()
        conduits[1].status = "abandoned"
        conduits[1].save()
        resp = api_client.get(
            "/api/plugins/pathways/geo/conduits/?exclude_status=retired&exclude_status=abandoned",
            format="json",
        )
        assert resp.json()["features"] == []

    def test_exclude_status_accepts_comma_separated_values(self, api_client, conduits):
        """The map frontend sends one comma-joined param."""
        conduits[0].status = "retired"
        conduits[0].save()
        conduits[1].status = "abandoned"
        conduits[1].save()
        resp = api_client.get(
            "/api/plugins/pathways/geo/conduits/?exclude_status=retired,abandoned",
            format="json",
        )
        assert resp.json()["features"] == []

    def test_exclude_status_changes_etag(self, api_client, conduits):
        conduits[0].status = "retired"
        conduits[0].save()
        plain = api_client.get("/api/plugins/pathways/geo/conduits/", format="json")
        excluded = api_client.get(
            "/api/plugins/pathways/geo/conduits/?exclude_status=retired",
            format="json",
        )
        assert plain["ETag"] != excluded["ETag"]

    def test_circuit_layer_ignores_exclude_status(self, api_client, db):
        # CircuitGeometry has no own status field; the param must not 500
        resp = api_client.get(
            "/api/plugins/pathways/geo/circuits/?exclude_status=retired",
            format="json",
        )
        assert resp.status_code == 200

    def test_info_counts_respect_exclude_status(self, api_client, structures, conduits):
        conduits[0].status = "retired"
        conduits[0].save()
        structures[0].status = "abandoned"
        structures[0].save()
        resp = api_client.get(
            "/api/plugins/pathways/geo/info/?exclude_status=retired&exclude_status=abandoned",
            format="json",
        )
        counts = resp.json()["counts"]
        assert counts["conduits"] == len(conduits) - 1
        assert counts["structures"] == len(structures) - 1

    def test_info_etag_varies_with_exclude_status(self, api_client, structures):
        plain = api_client.get("/api/plugins/pathways/geo/info/", format="json")
        excluded = api_client.get(
            "/api/plugins/pathways/geo/info/?exclude_status=retired",
            format="json",
        )
        assert plain["ETag"] != excluded["ETag"]

    def test_info_lists_available_statuses(self, api_client, db):
        resp = api_client.get("/api/plugins/pathways/geo/info/", format="json")
        statuses = resp.json()["statuses"]
        values = [s["value"] for s in statuses]
        assert "active" in values
        assert "retired" in values
        for s in statuses:
            assert set(s) == {"value", "label", "color"}


# ---------------------------------------------------------------------------
# GeoJSON API — /info endpoint
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMapInfoAPI:
    URL = "/api/plugins/pathways/geo/info/"

    def test_returns_counts_keys(self, api_client, structures, conduits, conduit_bank, aerial_span, direct_buried):
        resp = api_client.get(self.URL, format="json")
        assert resp.status_code == 200
        data = resp.json()
        assert "counts" in data
        counts = data["counts"]
        for key in ("structures", "conduit_banks", "conduits", "aerial_spans", "direct_buried", "circuits"):
            assert key in counts
            assert isinstance(counts[key], int)

    def test_counts_match_objects(self, api_client, structures, conduits, conduit_bank, aerial_span, direct_buried):
        resp = api_client.get(self.URL, format="json")
        counts = resp.json()["counts"]
        # Conduit endpoint excludes those in a bank; both fixture conduits stand alone
        assert counts["structures"] == len(structures)
        assert counts["conduit_banks"] == 1
        assert counts["conduits"] == len(conduits)
        assert counts["aerial_spans"] == 1
        assert counts["direct_buried"] == 1

    def test_empty_bbox(self, api_client, structures, conduits):
        # Bbox far from any feature
        resp = api_client.get(f"{self.URL}?bbox=170,80,171,81", format="json")
        assert resp.status_code == 200
        counts = resp.json()["counts"]
        assert counts["structures"] == 0
        assert counts["conduits"] == 0

    def test_bbox_filters_results(self, api_client, structures, conduits):
        # Without bbox we should see every feature
        full = api_client.get(self.URL, format="json").json()
        # A bbox far from any feature should match nothing
        far = api_client.get(f"{self.URL}?bbox=170,80,171,81", format="json").json()
        assert full["counts"]["structures"] >= far["counts"]["structures"]
        assert full["counts"]["structures"] > 0
        assert far["counts"]["structures"] == 0

    def test_etag_header_present(self, api_client, structures):
        resp = api_client.get(self.URL, format="json")
        assert resp.get("ETag")

    def test_etag_304_on_match(self, api_client, structures):
        resp1 = api_client.get(self.URL, format="json")
        etag = resp1["ETag"]
        resp2 = api_client.get(self.URL, format="json", HTTP_IF_NONE_MATCH=etag)
        assert resp2.status_code == 304

    def test_invalid_bbox_ignored(self, api_client, structures):
        resp = api_client.get(f"{self.URL}?bbox=garbage", format="json")
        assert resp.status_code == 200
        assert resp.json()["counts"]["structures"] >= len(structures)

    def test_excludes_banked_conduits(self, api_client, conduit_bank, srid):
        # A conduit that lives inside a bank should not be counted in "conduits"
        Conduit.objects.create(
            label="In-bank",
            conduit_bank=conduit_bank,
            bank_position="A1",
            path=LineString((100, 100), (300, 300), srid=srid),
            length=200,
        )
        resp = api_client.get(self.URL, format="json")
        counts = resp.json()["counts"]
        assert counts["conduit_banks"] == 1
        # The banked conduit is not counted in the conduits layer
        assert counts["conduits"] == 0

    def test_returns_bbox_when_supplied(self, api_client, structures):
        bbox = "-10,-10,10,10"
        resp = api_client.get(f"{self.URL}?bbox={bbox}", format="json")
        data = resp.json()
        assert data.get("bbox") == [-10.0, -10.0, 10.0, 10.0]

    def test_thresholds_in_response(self, api_client, structures):
        resp = api_client.get(self.URL, format="json")
        data = resp.json()
        assert "thresholds" in data
        t = data["thresholds"]
        assert t["structures"] == {"cluster": 200, "hide": 5000}
        for key in ("conduit_banks", "conduits", "aerial_spans", "direct_buried", "circuits"):
            assert t[key] == {"hide": 500}

    def test_plugin_config_threshold_override(self, api_client, structures, settings):
        # Shallow-merged per-layer key
        settings.PLUGINS_CONFIG = {
            **settings.PLUGINS_CONFIG,
            "netbox_pathways": {
                **settings.PLUGINS_CONFIG.get("netbox_pathways", {}),
                "map_thresholds": {"conduit_banks": {"hide": 1500}},
            },
        }
        resp = api_client.get(self.URL, format="json")
        t = resp.json()["thresholds"]
        assert t["conduit_banks"] == {"hide": 1500}
        # Other layers keep their defaults
        assert t["structures"] == {"cluster": 200, "hide": 5000}
        assert t["conduits"] == {"hide": 500}

    def test_external_reference_layer_counted(self, api_client, conduits):
        from netbox_pathways.models import Conduit
        from netbox_pathways.registry import LayerStyle, MapLayerRegistration, registry

        # Reference-mode layer: queryset of Conduits, geometry via start_structure FK
        registry.register(
            MapLayerRegistration(
                name="ext_ref",
                label="External Ref",
                geometry_type="Point",
                source="reference",
                queryset=lambda r: Conduit.objects.all(),
                geometry_field="start_structure",
                style=LayerStyle(color="#000"),
                max_features=42,
            )
        )
        try:
            resp = api_client.get(self.URL, format="json")
        finally:
            registry.unregister("ext_ref")
        data = resp.json()
        assert "external" in data["counts"]
        assert data["counts"]["external"]["ext_ref"] == len(conduits)
        assert data["thresholds"]["external"]["ext_ref"] == {"hide": 42}

    def test_url_mode_external_layer_omitted(self, api_client, structures):
        from netbox_pathways.registry import LayerStyle, MapLayerRegistration, registry

        registry.register(
            MapLayerRegistration(
                name="ext_url",
                label="External URL",
                geometry_type="LineString",
                source="url",
                url="https://example.com/layer.geojson",
                style=LayerStyle(color="#000"),
            )
        )
        try:
            resp = api_client.get(self.URL, format="json")
        finally:
            registry.unregister("ext_url")
        data = resp.json()
        # url-mode layers are not counted server-side
        assert "ext_url" not in data["counts"].get("external", {})
        assert "ext_url" not in data["thresholds"].get("external", {})


# ---------------------------------------------------------------------------
# MapView — _data_extent and _resolve_feature_extent
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMapViewExtent:
    def test_data_extent_with_structures(self, structures):
        from netbox_pathways.views import MapView

        view = MapView()
        extent = view._data_extent()
        assert extent is not None
        west, south, east, north = extent
        assert west <= east
        assert south <= north

    def test_data_extent_empty_db(self):
        from netbox_pathways.views import MapView

        # Delete all structures and pathways to test empty case
        Structure.objects.all().delete()
        view = MapView()
        view._data_extent()  # should not crash on empty DB

    def test_resolve_feature_extent_structure(self, structures):
        from netbox_pathways.views import MapView

        s = structures[0]
        extent = MapView._resolve_feature_extent(f"structure-{s.pk}")
        assert extent is not None
        west, south, east, north = extent
        assert -180 <= west <= 180
        assert -90 <= south <= 90

    def test_resolve_feature_extent_conduit(self, conduits):
        from netbox_pathways.views import MapView

        c = conduits[0]
        extent = MapView._resolve_feature_extent(f"conduit-{c.pk}")
        assert extent is not None

    def test_resolve_feature_extent_conduit_bank(self, conduit_bank):
        from netbox_pathways.views import MapView

        extent = MapView._resolve_feature_extent(f"conduit_bank-{conduit_bank.pk}")
        assert extent is not None

    def test_resolve_feature_extent_invalid_type(self):
        from netbox_pathways.views import MapView

        assert MapView._resolve_feature_extent("unknown-123") is None

    def test_resolve_feature_extent_invalid_format(self):
        from netbox_pathways.views import MapView

        assert MapView._resolve_feature_extent("noid") is None

    def test_resolve_feature_extent_missing_pk(self):
        from netbox_pathways.views import MapView

        assert MapView._resolve_feature_extent("structure-999999") is None

    def test_resolve_feature_extent_none(self):
        from netbox_pathways.views import MapView

        assert MapView._resolve_feature_extent(None) is None


# ---------------------------------------------------------------------------
# MapView.get — select param triggers feature extent
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMapViewSelect:
    def test_select_param_sets_bounds(self, structures):

        from django.test import RequestFactory

        from netbox_pathways.views import MapView

        factory = RequestFactory()
        s = structures[0]
        request = factory.get(f"/plugins/pathways/map/?select=structure-{s.pk}")
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()

        view = MapView()
        response = view.get(request)
        assert response.status_code == 200
        content = response.content.decode()
        # Should contain map_bounds JSON (not empty)
        assert "map_bounds" not in content or "[[" in content

    def test_select_param_invalid_uses_fallback(self):
        from unittest.mock import patch

        from django.test import RequestFactory

        from netbox_pathways.views import MapView

        factory = RequestFactory()
        request = factory.get("/plugins/pathways/map/?select=bad-999")
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()

        view = MapView()
        with patch.object(view, "_data_extent", return_value=None):
            response = view.get(request)
        assert response.status_code == 200

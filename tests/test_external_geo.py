"""Tests for the reference-mode external GeoJSON endpoint.

These require Django models to be available for FK introspection.
Run via: python -m pytest tests/test_external_geo.py -v
"""

import pytest

from netbox_pathways.api.external_geo import (
    _build_properties,
    _resolve_geo_column,
    resolve_geometry_expression,
)
from netbox_pathways.registry import LayerStyle, MapLayerRegistration, registry


@pytest.fixture(autouse=True)
def _clean_registry():
    registry.clear()
    yield
    registry.clear()


class TestResolveGeoColumn:
    """Test _resolve_geo_column with actual models."""

    def test_structure_fk_resolves(self):
        from netbox_pathways.models import Pathway

        # Pathway.start_structure is a FK to Structure
        col, label = _resolve_geo_column(Pathway, "start_structure")
        assert col == "start_structure__geometry"
        assert "structure" in label.lower()

    def test_site_fk_resolves_via_sitegeometry(self):
        from netbox_pathways.models import Structure

        # Structure.site is a FK to dcim.Site — resolves via SiteGeometry
        col, label = _resolve_geo_column(Structure, "site")
        assert col == "site__pathways_geometry__geometry"
        assert "site" in label.lower()

    def test_location_fk_resolves_via_identity_structure(self):
        from netbox_pathways.models import Pathway

        # Pathway.start_location is a FK to dcim.Location
        col, label = _resolve_geo_column(Pathway, "start_location")
        assert col == "start_location__pathways_structure__geometry"
        assert "location" in label.lower()

    def test_unsupported_fk_raises(self):
        from netbox_pathways.models import Conduit

        # Conduit.conduit_bank is a FK to ConduitBank — not in SUPPORTED_GEO_MODELS
        with pytest.raises(ValueError, match="not in SUPPORTED_GEO_MODELS"):
            _resolve_geo_column(Conduit, "conduit_bank")


def test_location_identity_accessor_matches_model():
    """The registry constant must track Structure.location's related_name;
    if they drift, endpoint snapping degrades silently (#90 follow-up)."""
    from netbox_pathways.models import Structure
    from netbox_pathways.registry import LOCATION_IDENTITY_ACCESSOR

    accessor = Structure._meta.get_field("location").remote_field.get_accessor_name()
    assert accessor == LOCATION_IDENTITY_ACCESSOR


class TestResolveGeometryExpression:
    def test_single_entry_returns_column_reference(self):
        from django.db.models import F

        from netbox_pathways.models import Pathway

        expr = resolve_geometry_expression(Pathway, "start_structure")
        assert isinstance(expr, F)
        assert expr.name == "start_structure__geometry"

    def test_tuple_coalesces_in_declared_order(self):
        from django.db.models.functions import Coalesce

        from netbox_pathways.models import Pathway

        expr = resolve_geometry_expression(Pathway, ("start_location", "start_structure"))
        assert isinstance(expr, Coalesce)
        names = [e.name for e in expr.get_source_expressions()]
        assert names == [
            "start_location__pathways_structure__geometry",
            "start_structure__geometry",
        ]

    def test_unresolvable_tuple_entry_raises(self):
        from netbox_pathways.models import Conduit

        with pytest.raises(ValueError, match="not in SUPPORTED_GEO_MODELS"):
            resolve_geometry_expression(Conduit, ("start_location", "conduit_bank"))


class TestBuildProperties:
    def test_explicit_fields(self):
        class FakeObj:
            pk = 42
            name = "Test"
            status = "active"
            secret = "hidden"

        props = _build_properties(FakeObj(), ["name", "status"], None)
        assert props == {"id": 42, "name": "Test", "status": "active"}
        assert "secret" not in props

    def test_fk_field_uses_str(self):
        class FakeRelated:
            pk = 7

            def __str__(self):
                return "Related Object"

        class FakeObj:
            pk = 42
            name = "Test"
            site = FakeRelated()

        props = _build_properties(FakeObj(), ["name", "site"], None)
        assert props["site"] == "Related Object"

    def test_none_field_preserved(self):
        class FakeObj:
            pk = 42
            name = "Test"
            status = None

        props = _build_properties(FakeObj(), ["name", "status"], None)
        assert props["status"] is None

    def test_auto_detect_uses_model_meta(self):
        """Auto-detect path with feature_fields=None uses model._meta."""
        from netbox_pathways.models import Structure

        # Create a minimal mock object with Structure's fields
        class FakeStructure:
            pk = 1
            name = "Test Structure"
            structure_type = "manhole"
            elevation = 100.0
            site = None

        props = _build_properties(FakeStructure(), None, Structure)
        assert props["id"] == 1
        assert props["name"] == "Test Structure"
        assert props["structure_type"] == "manhole"
        # Geometry field 'geometry' should be excluded
        assert "geometry" not in props


@pytest.mark.django_db
class TestExternalLayerGeoView:
    """The endpoint that serves reference-mode registered layers as GeoJSON."""

    URL = "/api/plugins/pathways/geo/external/ext_test/"

    @pytest.fixture
    def api_client(self, admin_user):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=admin_user)
        return client

    @pytest.fixture
    def conduit(self):
        from django.contrib.gis.geos import LineString, Point

        from netbox_pathways.geo import get_srid
        from netbox_pathways.models import Conduit, Structure

        srid = get_srid()
        s1 = Structure.objects.create(name="EXT-S1", geometry=Point(0, 0, srid=srid))
        s2 = Structure.objects.create(name="EXT-S2", geometry=Point(100, 100, srid=srid))
        return Conduit.objects.create(
            label="EXT-C1",
            start_structure=s1,
            end_structure=s2,
            path=LineString((0, 0), (100, 100), srid=srid),
        )

    @pytest.fixture
    def ext_layer(self, conduit):
        from netbox_pathways.models import Conduit

        registry.register(
            MapLayerRegistration(
                name="ext_test",
                label="External Test",
                geometry_type="Point",
                source="reference",
                queryset=lambda request: Conduit.objects.all(),
                geometry_field="start_structure",
                feature_fields=["label"],
                style=LayerStyle(color="#000"),
            )
        )

    def test_unknown_layer_returns_404(self, api_client):
        resp = api_client.get("/api/plugins/pathways/geo/external/nope/")
        assert resp.status_code == 404

    def test_reference_layer_serves_fk_geometry_as_features(self, api_client, conduit, ext_layer):
        """The layer's rows are serialized at their FK target's geometry, in
        WGS84, carrying the declared feature fields."""
        resp = api_client.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 1
        feat = data["features"][0]
        assert feat["properties"] == {"id": conduit.pk, "label": "EXT-C1"}
        lon, lat = feat["geometry"]["coordinates"]
        assert -180 <= lon <= 180
        assert -90 <= lat <= 90

    def test_bbox_excludes_far_features(self, api_client, conduit, ext_layer):
        resp = api_client.get(f"{self.URL}?bbox=170,80,171,81")
        assert resp.status_code == 200
        assert resp.json()["features"] == []


@pytest.mark.django_db
class TestLocationGeometryResolution:
    """Location-targeted layers serve the identity structure's geometry (#90)."""

    URL = "/api/plugins/pathways/geo/external/loc_test/"

    @pytest.fixture
    def api_client(self, admin_user):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=admin_user)
        return client

    @pytest.fixture
    def location_conduits(self):
        from dcim.models import Location, Site
        from django.contrib.gis.geos import LineString, Point

        from netbox_pathways.geo import get_srid
        from netbox_pathways.models import Conduit, Structure

        srid = get_srid()
        site = Site.objects.create(name="Geo-Site", slug="geo-site")
        loc_with = Location.objects.create(name="Handhole-7", slug="handhole-7", site=site)
        loc_without = Location.objects.create(name="Room-101", slug="room-101", site=site)
        anchor = Structure.objects.create(name="LOC-S0", geometry=Point(0, 0, srid=srid))
        identity = Structure.objects.create(
            name="LOC-HH7", geometry=Point(10, 20, srid=srid), site=site, location=loc_with
        )
        c_with = Conduit.objects.create(
            label="LOC-C1",
            start_structure=anchor,
            end_location=loc_with,
            path=LineString((0, 0), (10, 20), srid=srid),
        )
        c_without = Conduit.objects.create(
            label="LOC-C2",
            start_structure=anchor,
            end_location=loc_without,
            path=LineString((0, 0), (5, 5), srid=srid),
        )
        return c_with, c_without, identity

    @pytest.fixture
    def loc_layer(self):
        from netbox_pathways.models import Conduit

        registry.register(
            MapLayerRegistration(
                name="loc_test",
                label="Location Test",
                geometry_type="Point",
                source="reference",
                queryset=lambda request: Conduit.objects.all(),
                geometry_field="end_location",
                feature_fields=["label"],
                style=LayerStyle(color="#000"),
            )
        )

    def test_identity_structure_geometry_served(self, api_client, location_conduits, loc_layer):
        from netbox_pathways.geo import to_leaflet

        c_with, c_without, identity = location_conduits
        resp = api_client.get(self.URL)
        assert resp.status_code == 200
        features = resp.json()["features"]
        # The location without an identity structure resolves to NULL and is dropped.
        assert [f["properties"]["id"] for f in features] == [c_with.pk]
        expected = to_leaflet(identity.geometry)
        lon, lat = features[0]["geometry"]["coordinates"]
        assert lon == pytest.approx(expected.x)
        assert lat == pytest.approx(expected.y)

    @pytest.fixture
    def loc_fallback_layer(self):
        from netbox_pathways.models import Conduit

        registry.register(
            MapLayerRegistration(
                name="loc_test",
                label="Location Fallback",
                geometry_type="Point",
                source="reference",
                queryset=lambda request: Conduit.objects.all(),
                geometry_field=("end_location", "start_structure"),
                feature_fields=["label"],
                style=LayerStyle(color="#000"),
            )
        )

    def test_tuple_falls_back_instead_of_dropping(self, api_client, location_conduits, loc_fallback_layer):
        """A location without an identity structure degrades to the next
        entry's geometry rather than vanishing from the map (#90)."""
        c_with, c_without, identity = location_conduits
        resp = api_client.get(self.URL)
        assert resp.status_code == 200
        features = {f["properties"]["id"]: f for f in resp.json()["features"]}
        assert set(features) == {c_with.pk, c_without.pk}
        # c_with resolves through the location's identity structure...
        from netbox_pathways.geo import to_leaflet

        expected = to_leaflet(identity.geometry)
        assert features[c_with.pk]["geometry"]["coordinates"][0] == pytest.approx(expected.x)
        # ...while c_without falls back to its start structure at the origin.
        anchor = to_leaflet(c_without.start_structure.geometry)
        assert features[c_without.pk]["geometry"]["coordinates"][0] == pytest.approx(anchor.x)

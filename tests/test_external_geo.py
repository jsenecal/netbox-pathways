"""Tests for the reference-mode external GeoJSON endpoint.

These require Django models to be available for FK introspection.
Run via: python -m pytest tests/test_external_geo.py -v
"""

import pytest

from netbox_pathways.api.external_geo import _build_properties, _resolve_geo_column
from netbox_pathways.registry import registry


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
        assert col == "start_structure__location"
        assert "structure" in label.lower()

    def test_site_fk_resolves_via_sitegeometry(self):
        from netbox_pathways.models import Structure

        # Structure.site is a FK to dcim.Site — resolves via SiteGeometry
        col, label = _resolve_geo_column(Structure, "site")
        assert col == "site__pathways_geometry__geometry"
        assert "site" in label.lower()

    def test_unsupported_fk_raises(self):
        from netbox_pathways.models import Conduit

        # Conduit.conduit_bank is a FK to ConduitBank — not in SUPPORTED_GEO_MODELS
        with pytest.raises(ValueError, match="not in SUPPORTED_GEO_MODELS"):
            _resolve_geo_column(Conduit, "conduit_bank")


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
        # Geometry field 'location' should be excluded
        assert "location" not in props

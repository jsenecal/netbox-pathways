import pytest

from netbox_pathways.registry import (
    LayerDetail,
    LayerStyle,
    register_map_layer,
    registry,
    unregister_map_layer,
)


class TestRegistration:
    def test_register_url_layer(self, url_layer_kwargs):
        layer = register_map_layer(**url_layer_kwargs)
        assert layer.name == "test_cables"
        assert "test_cables" in registry
        assert len(registry) == 1

    def test_register_reference_layer(self, ref_layer_kwargs):
        layer = register_map_layer(**ref_layer_kwargs)
        assert layer.name == "test_points"
        assert layer.source == "reference"

    def test_duplicate_name_raises(self, url_layer_kwargs):
        register_map_layer(**url_layer_kwargs)
        with pytest.raises(ValueError, match="already registered"):
            register_map_layer(**url_layer_kwargs)

    def test_invalid_geometry_type(self, url_layer_kwargs):
        url_layer_kwargs["geometry_type"] = "MultiPoint"
        with pytest.raises(ValueError, match="Invalid geometry_type"):
            register_map_layer(**url_layer_kwargs)

    def test_invalid_source(self, url_layer_kwargs):
        url_layer_kwargs["source"] = "magic"
        with pytest.raises(ValueError, match="Invalid source"):
            register_map_layer(**url_layer_kwargs)

    def test_url_mode_requires_url(self, url_layer_kwargs):
        url_layer_kwargs["url"] = ""
        with pytest.raises(ValueError, match="require a 'url'"):
            register_map_layer(**url_layer_kwargs)

    def test_reference_mode_requires_queryset(self, ref_layer_kwargs):
        ref_layer_kwargs["queryset"] = None
        with pytest.raises(ValueError, match="require a 'queryset'"):
            register_map_layer(**ref_layer_kwargs)

    def test_reference_mode_requires_geometry_field(self, ref_layer_kwargs):
        ref_layer_kwargs["geometry_field"] = ""
        with pytest.raises(ValueError, match="require a 'geometry_field'"):
            register_map_layer(**ref_layer_kwargs)

    def test_color_field_must_be_in_feature_fields(self, ref_layer_kwargs):
        ref_layer_kwargs["style"] = LayerStyle(
            color_field="status",
            color_map={"active": "#0f0"},
        )
        ref_layer_kwargs["feature_fields"] = ["name"]  # missing 'status'
        with pytest.raises(ValueError, match="color_field.*must be included"):
            register_map_layer(**ref_layer_kwargs)

    def test_color_field_ok_when_feature_fields_none(self, ref_layer_kwargs):
        ref_layer_kwargs["style"] = LayerStyle(
            color_field="status",
            color_map={"active": "#0f0"},
        )
        # feature_fields defaults to None — no validation needed
        layer = register_map_layer(**ref_layer_kwargs)
        assert layer.style.color_field == "status"


class TestUnregister:
    def test_unregister(self, url_layer_kwargs):
        register_map_layer(**url_layer_kwargs)
        assert len(registry) == 1
        unregister_map_layer("test_cables")
        assert len(registry) == 0

    def test_unregister_missing_is_noop(self):
        unregister_map_layer("nonexistent")  # no error


class TestClear:
    def test_clear(self, url_layer_kwargs, ref_layer_kwargs):
        register_map_layer(**url_layer_kwargs)
        register_map_layer(**ref_layer_kwargs)
        assert len(registry) == 2
        registry.clear()
        assert len(registry) == 0


class TestOrdering:
    def test_all_sorted_by_sort_order_then_name(self):
        register_map_layer(
            name="z_layer",
            label="Z",
            geometry_type="Point",
            source="url",
            url="/z/",
            sort_order=0,
        )
        register_map_layer(
            name="a_layer",
            label="A",
            geometry_type="Point",
            source="url",
            url="/a/",
            sort_order=0,
        )
        register_map_layer(
            name="m_layer",
            label="M",
            geometry_type="Point",
            source="url",
            url="/m/",
            sort_order=-1,
        )
        names = [layer.name for layer in registry.all()]
        assert names == ["m_layer", "a_layer", "z_layer"]


class TestToJson:
    def test_url_layer_json(self, url_layer_kwargs):
        layer = register_map_layer(**url_layer_kwargs)
        data = layer.to_json()
        assert data["name"] == "test_cables"
        assert data["url"] == "/api/plugins/test/geo/cables/"
        assert data["style"]["color"] == "#e65100"
        assert data["style"]["dash"] == "10 5"
        assert "detail" not in data

    def test_reference_layer_json_auto_url(self, ref_layer_kwargs):
        layer = register_map_layer(**ref_layer_kwargs)
        data = layer.to_json()
        assert data["url"] == "/api/plugins/pathways/geo/external/test_points/"
        assert data["detail"]["urlTemplate"] == "/api/plugins/test/points/{id}/"
        assert data["detail"]["fields"] == ["name", "status"]

    def test_detail_url_in_json(self, ref_layer_kwargs):
        ref_layer_kwargs["detail"] = LayerDetail(
            url_template="/plugins/test/points/{id}/",
            detail_url="/api/plugins/test/points/{id}/card/",
            fields=["name"],
        )
        layer = register_map_layer(**ref_layer_kwargs)
        data = layer.to_json()
        assert data["detail"]["detailUrl"] == "/api/plugins/test/points/{id}/card/"
        assert data["detail"]["urlTemplate"] == "/plugins/test/points/{id}/"

    def test_json_camel_case_keys(self, url_layer_kwargs):
        layer = register_map_layer(**url_layer_kwargs)
        data = layer.to_json()
        assert "geometryType" in data
        assert "defaultVisible" in data
        assert "popoverFields" in data
        assert "minZoom" in data
        assert "sortOrder" in data

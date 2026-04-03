# Map Layer Registry Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow external NetBox plugins to register map layers (points, lines, polygons) that render on the pathways map with configurable styling, sidebar detail panels, and popover tooltips.

**Architecture:** Python-side registry populated during `ready()`, serialized to JSON config for the JS map. Two geometry modes: URL (plugin owns GeoJSON endpoint) and reference (pathways resolves geometry from FK). No JS-side registration — everything driven by config.

**Tech Stack:** Python 3.12, Django 5.2, djangorestframework-gis, TypeScript, Leaflet, esbuild

**Spec:** `docs/superpowers/specs/2026-03-19-map-layer-registry-design.md`

---

## File Structure

### New files
| File | Responsibility |
|---|---|
| `netbox_pathways/registry.py` | `MapLayerRegistry` singleton, dataclasses (`LayerStyle`, `LayerDetail`, `MapLayerRegistration`), `register_map_layer()`, `unregister_map_layer()`, `SUPPORTED_GEO_MODELS` |
| `netbox_pathways/api/external_geo.py` | Reference-mode GeoJSON viewset — resolves geometry from FK, bbox filters, serializes |
| `tests/test_registry.py` | Unit tests for registry validation, registration, deduplication |
| `tests/test_external_geo.py` | API tests for the reference-mode endpoint |
| `tests/conftest.py` | Shared pytest fixtures (user, API client, sample data) |
| `netbox_pathways/static/netbox_pathways/src/external-layers.ts` | Module for fetching/rendering external layers — imported by pathways-map.ts |
| `netbox_pathways/static/netbox_pathways/src/types/external.ts` | `ExternalLayerConfig` interface and related types |

### Modified files
| File | Changes |
|---|---|
| `netbox_pathways/views.py` | `MapView.get_extra_context()` reads registry, serializes `externalLayers` into config |
| `netbox_pathways/api/urls.py` | Add route for `/geo/external/<layer_name>/` |
| `netbox_pathways/static/netbox_pathways/src/pathways-map.ts` | Import external-layers module, wire into `_loadData()` cycle |
| `netbox_pathways/static/netbox_pathways/src/sidebar.ts` | Support external layer detail panels, type filter pills, generic field rendering |
| `netbox_pathways/static/netbox_pathways/src/popover.ts` | Accept `popover_fields` config instead of hardcoded name+type |
| `netbox_pathways/static/netbox_pathways/src/types/features.ts` | Widen `FeatureType` to `string`, keep native constants |
| `netbox_pathways/static/netbox_pathways/src/types/netbox.d.ts` | Add `externalLayers` to `PathwaysConfig` interface |
| `netbox_pathways/templates/netbox_pathways/map.html` | No changes needed (config already passed as JSON) |

---

## Chunk 1: Python Registry

### Task 1: Create registry dataclasses and registry singleton

**Files:**
- Create: `netbox_pathways/registry.py`

- [ ] **Step 1: Create `registry.py` with dataclasses and registry**

```python
"""Map layer registry for cross-plugin map integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest

logger = logging.getLogger(__name__)

# Maps FK target model label → geometry column name on that model.
SUPPORTED_GEO_MODELS: dict[str, str] = {
    'netbox_pathways.Structure': 'location',
    'netbox_pathways.SiteGeometry': 'geometry',
}


@dataclass(frozen=True)
class LayerStyle:
    """Visual styling for a map layer."""
    color: str = '#795548'
    color_field: str | None = None
    color_map: dict[str, str] | None = None
    default_color: str = '#795548'
    icon: str | None = None
    dash: str | None = None
    weight: int = 3
    opacity: float = 0.7


@dataclass(frozen=True)
class LayerDetail:
    """Sidebar detail panel configuration."""
    url_template: str = ''
    fields: list[str] = field(default_factory=list)
    label_field: str = 'name'


@dataclass
class MapLayerRegistration:
    """A registered external map layer."""
    name: str
    label: str
    geometry_type: str  # 'Point', 'LineString', 'Polygon'
    source: str  # 'url' or 'reference'

    # URL mode
    url: str = ''

    # Reference mode
    queryset: Callable[[HttpRequest], QuerySet] | None = None
    geometry_field: str = ''
    feature_fields: list[str] | None = None

    # Display
    style: LayerStyle = field(default_factory=LayerStyle)
    detail: LayerDetail | None = None
    popover_fields: list[str] = field(default_factory=lambda: ['name'])
    default_visible: bool = False
    group: str = 'External'
    min_zoom: int = 11
    max_zoom: int | None = None
    sort_order: int = 0

    def to_json(self, api_base: str = '/api/plugins/pathways/geo/') -> dict[str, Any]:
        """Serialize to JSON-safe dict for PATHWAYS_CONFIG."""
        url = self.url
        if self.source == 'reference':
            url = f'{api_base}external/{self.name}/'

        data: dict[str, Any] = {
            'name': self.name,
            'label': self.label,
            'geometryType': self.geometry_type,
            'url': url,
            'style': {
                'color': self.style.color,
                'colorField': self.style.color_field,
                'colorMap': self.style.color_map,
                'defaultColor': self.style.default_color,
                'icon': self.style.icon,
                'dash': self.style.dash,
                'weight': self.style.weight,
                'opacity': self.style.opacity,
            },
            'popoverFields': self.popover_fields,
            'defaultVisible': self.default_visible,
            'group': self.group,
            'minZoom': self.min_zoom,
            'maxZoom': self.max_zoom,
            'sortOrder': self.sort_order,
        }
        if self.detail:
            data['detail'] = {
                'urlTemplate': self.detail.url_template,
                'fields': self.detail.fields,
                'labelField': self.detail.label_field,
            }
        return data


_VALID_GEOMETRY_TYPES = {'Point', 'LineString', 'Polygon'}
_VALID_SOURCES = {'url', 'reference'}


class MapLayerRegistry:
    """Singleton registry for external map layers."""

    def __init__(self) -> None:
        self._layers: dict[str, MapLayerRegistration] = {}

    def register(self, layer: MapLayerRegistration) -> None:
        if layer.name in self._layers:
            raise ValueError(f"Map layer '{layer.name}' is already registered.")
        if layer.geometry_type not in _VALID_GEOMETRY_TYPES:
            raise ValueError(
                f"Invalid geometry_type '{layer.geometry_type}'. "
                f"Must be one of {_VALID_GEOMETRY_TYPES}."
            )
        if layer.source not in _VALID_SOURCES:
            raise ValueError(
                f"Invalid source '{layer.source}'. Must be one of {_VALID_SOURCES}."
            )
        if layer.source == 'url' and not layer.url:
            raise ValueError("URL-mode layers require a 'url'.")
        if layer.source == 'reference':
            if layer.queryset is None:
                raise ValueError("Reference-mode layers require a 'queryset' callable.")
            if not layer.geometry_field:
                raise ValueError("Reference-mode layers require a 'geometry_field'.")
        if (
            layer.style.color_field
            and layer.feature_fields is not None
            and layer.style.color_field not in layer.feature_fields
        ):
            raise ValueError(
                f"color_field '{layer.style.color_field}' must be included "
                f"in feature_fields."
            )
        self._layers[layer.name] = layer
        logger.info("Registered map layer '%s' (%s)", layer.name, layer.source)

    def unregister(self, name: str) -> None:
        self._layers.pop(name, None)

    def clear(self) -> None:
        self._layers.clear()

    def get(self, name: str) -> MapLayerRegistration | None:
        return self._layers.get(name)

    def all(self) -> list[MapLayerRegistration]:
        return sorted(self._layers.values(), key=lambda l: (l.sort_order, l.name))

    def __len__(self) -> int:
        return len(self._layers)

    def __contains__(self, name: str) -> bool:
        return name in self._layers


# Module-level singleton — populated during ready(), cleared on restart.
# Note: geometry_field FK validation is intentionally deferred to request time
# (in ExternalLayerGeoView) rather than registration time, because models may
# not be fully loaded during the ready() phase.
registry = MapLayerRegistry()


def register_map_layer(**kwargs: Any) -> MapLayerRegistration:
    """Convenience function for registering a map layer.

    Usage::

        register_map_layer(
            name='splice_points',
            label='Splice Points',
            geometry_type='Point',
            source='reference',
            queryset=lambda r: SplicePoint.objects.restrict(r.user, 'view'),
            geometry_field='structure',
            style=LayerStyle(color='#2e7d32', icon='mdi-connection'),
        )
    """
    layer = MapLayerRegistration(**kwargs)
    registry.register(layer)
    return layer


def unregister_map_layer(name: str) -> None:
    """Remove a layer from the registry (mainly for testing)."""
    registry.unregister(name)
```

- [ ] **Step 2: Verify module imports cleanly**

Run: `cd /opt/netbox-pathways && python -c "from netbox_pathways.registry import register_map_layer, LayerStyle, LayerDetail, registry; print('OK', len(registry))"`
Expected: `OK 0`

- [ ] **Step 3: Commit**

```bash
git add netbox_pathways/registry.py
git commit -m "feat(registry): add map layer registry dataclasses and singleton"
```

---

### Task 2: Test the registry

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_registry.py`

- [ ] **Step 1: Create test infrastructure**

`tests/__init__.py` — empty file.

`tests/conftest.py`:
```python
import pytest

from netbox_pathways.registry import LayerDetail, LayerStyle, registry


@pytest.fixture(autouse=True)
def _clean_registry():
    """Ensure each test starts with a clean registry."""
    registry.clear()
    yield
    registry.clear()


@pytest.fixture()
def url_layer_kwargs():
    return dict(
        name='test_cables',
        label='Test Cables',
        geometry_type='LineString',
        source='url',
        url='/api/plugins/test/geo/cables/',
        style=LayerStyle(color='#e65100', dash='10 5'),
    )


@pytest.fixture()
def ref_layer_kwargs():
    return dict(
        name='test_points',
        label='Test Points',
        geometry_type='Point',
        source='reference',
        queryset=lambda request: None,  # stub
        geometry_field='structure',
        style=LayerStyle(color='#2e7d32', icon='mdi-circle'),
        detail=LayerDetail(
            url_template='/api/plugins/test/points/{id}/',
            fields=['name', 'status'],
        ),
    )
```

- [ ] **Step 2: Write registry unit tests**

`tests/test_registry.py`:
```python
import pytest

from netbox_pathways.registry import (
    LayerDetail,
    LayerStyle,
    MapLayerRegistration,
    register_map_layer,
    registry,
    unregister_map_layer,
)


class TestRegistration:
    def test_register_url_layer(self, url_layer_kwargs):
        layer = register_map_layer(**url_layer_kwargs)
        assert layer.name == 'test_cables'
        assert 'test_cables' in registry
        assert len(registry) == 1

    def test_register_reference_layer(self, ref_layer_kwargs):
        layer = register_map_layer(**ref_layer_kwargs)
        assert layer.name == 'test_points'
        assert layer.source == 'reference'

    def test_duplicate_name_raises(self, url_layer_kwargs):
        register_map_layer(**url_layer_kwargs)
        with pytest.raises(ValueError, match="already registered"):
            register_map_layer(**url_layer_kwargs)

    def test_invalid_geometry_type(self, url_layer_kwargs):
        url_layer_kwargs['geometry_type'] = 'MultiPoint'
        with pytest.raises(ValueError, match="Invalid geometry_type"):
            register_map_layer(**url_layer_kwargs)

    def test_invalid_source(self, url_layer_kwargs):
        url_layer_kwargs['source'] = 'magic'
        with pytest.raises(ValueError, match="Invalid source"):
            register_map_layer(**url_layer_kwargs)

    def test_url_mode_requires_url(self, url_layer_kwargs):
        url_layer_kwargs['url'] = ''
        with pytest.raises(ValueError, match="require a 'url'"):
            register_map_layer(**url_layer_kwargs)

    def test_reference_mode_requires_queryset(self, ref_layer_kwargs):
        ref_layer_kwargs['queryset'] = None
        with pytest.raises(ValueError, match="require a 'queryset'"):
            register_map_layer(**ref_layer_kwargs)

    def test_reference_mode_requires_geometry_field(self, ref_layer_kwargs):
        ref_layer_kwargs['geometry_field'] = ''
        with pytest.raises(ValueError, match="require a 'geometry_field'"):
            register_map_layer(**ref_layer_kwargs)

    def test_color_field_must_be_in_feature_fields(self, ref_layer_kwargs):
        ref_layer_kwargs['style'] = LayerStyle(
            color_field='status',
            color_map={'active': '#0f0'},
        )
        ref_layer_kwargs['feature_fields'] = ['name']  # missing 'status'
        with pytest.raises(ValueError, match="color_field.*must be included"):
            register_map_layer(**ref_layer_kwargs)

    def test_color_field_ok_when_feature_fields_none(self, ref_layer_kwargs):
        ref_layer_kwargs['style'] = LayerStyle(
            color_field='status',
            color_map={'active': '#0f0'},
        )
        # feature_fields defaults to None — no validation needed
        layer = register_map_layer(**ref_layer_kwargs)
        assert layer.style.color_field == 'status'


class TestUnregister:
    def test_unregister(self, url_layer_kwargs):
        register_map_layer(**url_layer_kwargs)
        assert len(registry) == 1
        unregister_map_layer('test_cables')
        assert len(registry) == 0

    def test_unregister_missing_is_noop(self):
        unregister_map_layer('nonexistent')  # no error


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
            name='z_layer', label='Z', geometry_type='Point',
            source='url', url='/z/', sort_order=0,
        )
        register_map_layer(
            name='a_layer', label='A', geometry_type='Point',
            source='url', url='/a/', sort_order=0,
        )
        register_map_layer(
            name='m_layer', label='M', geometry_type='Point',
            source='url', url='/m/', sort_order=-1,
        )
        names = [l.name for l in registry.all()]
        assert names == ['m_layer', 'a_layer', 'z_layer']


class TestToJson:
    def test_url_layer_json(self, url_layer_kwargs):
        layer = register_map_layer(**url_layer_kwargs)
        data = layer.to_json()
        assert data['name'] == 'test_cables'
        assert data['url'] == '/api/plugins/test/geo/cables/'
        assert data['style']['color'] == '#e65100'
        assert data['style']['dash'] == '10 5'
        assert 'detail' not in data

    def test_reference_layer_json_auto_url(self, ref_layer_kwargs):
        layer = register_map_layer(**ref_layer_kwargs)
        data = layer.to_json()
        assert data['url'] == '/api/plugins/pathways/geo/external/test_points/'
        assert data['detail']['urlTemplate'] == '/api/plugins/test/points/{id}/'
        assert data['detail']['fields'] == ['name', 'status']

    def test_json_camel_case_keys(self, url_layer_kwargs):
        layer = register_map_layer(**url_layer_kwargs)
        data = layer.to_json()
        assert 'geometryType' in data
        assert 'defaultVisible' in data
        assert 'popoverFields' in data
        assert 'minZoom' in data
        assert 'sortOrder' in data
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `cd /opt/netbox-pathways && python -m pytest tests/test_registry.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "tests(registry): add unit tests for map layer registry"
```

---

### Task 3: Wire registry into MapView

**Files:**
- Modify: `netbox_pathways/views.py` (MapView.get_extra_context, ~line 654)

- [ ] **Step 1: Add externalLayers to pathways_config in get_extra_context()**

In `views.py`, inside `get_extra_context()`, after the line that sets `pathways_config['baseLayers']`, add:

```python
from netbox_pathways.registry import registry as map_layer_registry

# ... inside get_extra_context(), after baseLayers line:
pathways_config['externalLayers'] = [
    layer.to_json(api_base=pathways_config['apiBase'])
    for layer in map_layer_registry.all()
]
```

The import goes at the top of the file with the other imports.

- [ ] **Step 2: Verify the view still loads without errors**

Run: `cd /opt/netbox-pathways && python -c "from netbox_pathways.views import MapView; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add netbox_pathways/views.py
git commit -m "feat(views): serialize external map layers into PATHWAYS_CONFIG"
```

---

## Chunk 2: Reference-Mode GeoJSON Endpoint

### Task 4: Create the external layer GeoJSON viewset

**Files:**
- Create: `netbox_pathways/api/external_geo.py`
- Modify: `netbox_pathways/api/urls.py`

- [ ] **Step 1: Create `external_geo.py`**

```python
"""GeoJSON endpoint for reference-mode external map layers.

Resolves geometry by joining through the FK declared in the layer
registration, transforms to WGS84, applies bbox filtering, and returns
a standard GeoJSON FeatureCollection.
"""

from __future__ import annotations

import logging

from django.contrib.gis.db.models.functions import Transform
from django.contrib.gis.geos import Polygon
from django.http import Http404, JsonResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from netbox_pathways.api.geo import MAX_GEO_RESULTS
from netbox_pathways.geo import LEAFLET_SRID
from netbox_pathways.registry import SUPPORTED_GEO_MODELS, registry

logger = logging.getLogger(__name__)


def _resolve_geo_column(model, geometry_field: str) -> tuple[str, str]:
    """Return (fk_field__geo_column, target_model_label) for the FK.

    Raises ValueError if the FK target is not in SUPPORTED_GEO_MODELS.
    """
    fk = model._meta.get_field(geometry_field)
    target = fk.related_model
    target_label = f'{target._meta.app_label}.{target._meta.model_name}'
    # Case-insensitive lookup to tolerate label casing
    for supported_label, geo_col in SUPPORTED_GEO_MODELS.items():
        if supported_label.lower() == target_label.lower():
            return f'{geometry_field}__{geo_col}', supported_label
    raise ValueError(
        f"FK '{geometry_field}' on {model.__name__} points to "
        f"{target_label}, which is not in SUPPORTED_GEO_MODELS."
    )


def _build_properties(obj, feature_fields: list[str] | None, model) -> dict:
    """Build GeoJSON properties dict from model instance."""
    props: dict = {'id': obj.pk}

    if feature_fields is not None:
        fields_to_use = feature_fields
    else:
        # Auto-detect scalar fields + FK display values
        fields_to_use = []
        for f in model._meta.get_fields():
            if not hasattr(f, 'column'):
                continue  # skip reverse relations, M2M, etc.
            if hasattr(f, 'geo_cols'):
                continue  # skip geometry fields
            fields_to_use.append(f.name)

    for fname in fields_to_use:
        val = getattr(obj, fname, None)
        # FK → use __str__ of related object
        if hasattr(val, 'pk'):
            props[fname] = str(val)
        elif val is not None:
            props[fname] = val
        else:
            props[fname] = None
    return props


class ExternalLayerGeoView(APIView):
    """Serve GeoJSON for a reference-mode registered layer."""

    permission_classes = [IsAuthenticated]

    def get(self, request, layer_name: str):
        layer_reg = registry.get(layer_name)
        if layer_reg is None or layer_reg.source != 'reference':
            raise Http404(f"No reference-mode layer named '{layer_name}'.")

        qs = layer_reg.queryset(request)
        model = qs.model

        fk_geo_path, _target_label = _resolve_geo_column(
            model, layer_reg.geometry_field,
        )

        # Annotate with WGS84 geometry
        qs = qs.annotate(
            _geo_4326=Transform(fk_geo_path, LEAFLET_SRID),
        ).exclude(_geo_4326__isnull=True)

        # Bbox filtering
        bbox_str = request.query_params.get('bbox', '')
        if bbox_str:
            try:
                w, s, e, n = (float(x) for x in bbox_str.split(','))
                bbox_poly = Polygon.from_bbox((w, s, e, n))
                bbox_poly.srid = LEAFLET_SRID
                qs = qs.filter(_geo_4326__intersects=bbox_poly)
            except (ValueError, TypeError):
                pass  # ignore malformed bbox

        qs = qs[:MAX_GEO_RESULTS]

        features = []
        for obj in qs:
            geom = obj._geo_4326
            if geom is None:
                continue
            props = _build_properties(obj, layer_reg.feature_fields, model)
            features.append({
                'type': 'Feature',
                'geometry': {
                    'type': geom.geom_type,
                    'coordinates': geom.coords,
                },
                'properties': props,
            })

        return JsonResponse({
            'type': 'FeatureCollection',
            'features': features,
        })
```

- [ ] **Step 2: Add URL route in `api/urls.py`**

Add this import and URL pattern to `netbox_pathways/api/urls.py`:

```python
from netbox_pathways.api.external_geo import ExternalLayerGeoView
```

In the `urlpatterns` list, add:

```python
path('geo/external/<str:layer_name>/', ExternalLayerGeoView.as_view(), name='external-geo'),
```

- [ ] **Step 3: Verify URL resolves**

Run: `cd /opt/netbox-pathways && python -c "from netbox_pathways.api.urls import urlpatterns; print([p.name for p in urlpatterns if hasattr(p, 'name')])"`
Expected: list includes `'external-geo'`

- [ ] **Step 4: Commit**

```bash
git add netbox_pathways/api/external_geo.py netbox_pathways/api/urls.py
git commit -m "feat(api): add reference-mode GeoJSON endpoint for external layers"
```

---

### Task 5: Test the external GeoJSON endpoint

**Files:**
- Create: `tests/test_external_geo.py`

- [ ] **Step 1: Write endpoint tests**

These tests require the full Django test harness since they hit the API. They use the NetBox test utilities.

`tests/test_external_geo.py`:
```python
"""Tests for the reference-mode external GeoJSON endpoint.

These require the Django test database with PostGIS. Run via:
    python -m pytest tests/test_external_geo.py -v
"""

import pytest
from django.test import RequestFactory

from netbox_pathways.api.external_geo import _build_properties, _resolve_geo_column
from netbox_pathways.registry import (
    LayerStyle,
    MapLayerRegistration,
    register_map_layer,
    registry,
)


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
        col, label = _resolve_geo_column(Pathway, 'start_structure')
        assert col == 'start_structure__location'
        assert 'structure' in label.lower()

    def test_unsupported_fk_raises(self):
        from netbox_pathways.models import Structure

        # Structure.site is a FK to dcim.Site — not in SUPPORTED_GEO_MODELS
        with pytest.raises(ValueError, match="not in SUPPORTED_GEO_MODELS"):
            _resolve_geo_column(Structure, 'site')


class TestBuildProperties:
    def test_explicit_fields(self):
        class FakeObj:
            pk = 42
            name = 'Test'
            status = 'active'
            secret = 'hidden'

        props = _build_properties(FakeObj(), ['name', 'status'], None)
        assert props == {'id': 42, 'name': 'Test', 'status': 'active'}
        assert 'secret' not in props

    def test_fk_field_uses_str(self):
        class FakeRelated:
            pk = 7
            def __str__(self):
                return 'Related Object'

        class FakeObj:
            pk = 42
            name = 'Test'
            site = FakeRelated()

        props = _build_properties(FakeObj(), ['name', 'site'], None)
        assert props['site'] == 'Related Object'

    def test_none_field_preserved(self):
        class FakeObj:
            pk = 42
            name = 'Test'
            status = None

        props = _build_properties(FakeObj(), ['name', 'status'], None)
        assert props['status'] is None

    def test_auto_detect_uses_model_meta(self):
        """Auto-detect path with feature_fields=None uses model._meta."""
        from netbox_pathways.models import Structure

        # Create a minimal mock object with Structure's fields
        class FakeStructure:
            pk = 1
            name = 'Test Structure'
            structure_type = 'manhole'
            elevation = 100.0
            site = None

        props = _build_properties(FakeStructure(), None, Structure)
        assert props['id'] == 1
        assert props['name'] == 'Test Structure'
        assert props['structure_type'] == 'manhole'
        # Geometry field 'location' should be excluded
        assert 'location' not in props
```

- [ ] **Step 2: Run tests**

Run: `cd /opt/netbox-pathways && python -m pytest tests/test_external_geo.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_external_geo.py
git commit -m "tests(api): add tests for external layer GeoJSON endpoint"
```

---

## Chunk 3: TypeScript Types and External Layer Module

### Task 6: Add TypeScript types for external layers

**Files:**
- Create: `netbox_pathways/static/netbox_pathways/src/types/external.ts`
- Modify: `netbox_pathways/static/netbox_pathways/src/types/netbox.d.ts`
- Modify: `netbox_pathways/static/netbox_pathways/src/types/features.ts`

- [ ] **Step 1: Create `types/external.ts`**

```typescript
export interface ExternalLayerStyle {
  color: string;
  colorField: string | null;
  colorMap: Record<string, string> | null;
  defaultColor: string;
  icon: string | null;
  dash: string | null;
  weight: number;
  opacity: number;
}

export interface ExternalLayerDetail {
  urlTemplate: string;
  fields: string[];
  labelField: string;
}

export interface ExternalLayerConfig {
  name: string;
  label: string;
  geometryType: 'Point' | 'LineString' | 'Polygon';
  url: string;
  style: ExternalLayerStyle;
  detail?: ExternalLayerDetail;
  popoverFields: string[];
  defaultVisible: boolean;
  group: string;
  minZoom: number;
  maxZoom: number | null;
  sortOrder: number;
}
```

- [ ] **Step 2: Add `externalLayers` to `PathwaysConfig` in `netbox.d.ts`**

In the `PathwaysConfig` interface, add after the `baseLayers` line:

```typescript
externalLayers?: ExternalLayerConfig[];
```

Also add the import type reference at the top of the file (or use inline since it's a `.d.ts`):

```typescript
interface ExternalLayerConfig {
  name: string;
  label: string;
  geometryType: 'Point' | 'LineString' | 'Polygon';
  url: string;
  style: {
    color: string;
    colorField: string | null;
    colorMap: Record<string, string> | null;
    defaultColor: string;
    icon: string | null;
    dash: string | null;
    weight: number;
    opacity: number;
  };
  detail?: {
    urlTemplate: string;
    fields: string[];
    labelField: string;
  };
  popoverFields: string[];
  defaultVisible: boolean;
  group: string;
  minZoom: number;
  maxZoom: number | null;
  sortOrder: number;
}
```

Note: Since `netbox.d.ts` uses `declare global`, the `ExternalLayerConfig` interface should be declared in the same global scope so it's available everywhere without imports.

- [ ] **Step 3: Widen `FeatureType` in `features.ts`**

Change:
```typescript
export type FeatureType = 'structure' | 'conduit' | 'aerial' | 'direct_buried';
```
To:
```typescript
// Native layer types (used internally for styling/detail lookups)
export const NATIVE_TYPES = ['structure', 'conduit', 'aerial', 'direct_buried'] as const;
export type NativeFeatureType = typeof NATIVE_TYPES[number];

// Any feature type — includes external layer names
export type FeatureType = string;
```

- [ ] **Step 4: Type-check**

Run: `cd /opt/netbox-pathways/netbox_pathways/static/netbox_pathways && npx tsc --noEmit`
Expected: No errors (or only pre-existing errors unrelated to these changes)

- [ ] **Step 5: Commit**

```bash
git add netbox_pathways/static/netbox_pathways/src/types/
git commit -m "feat(types): add ExternalLayerConfig types, widen FeatureType"
```

---

### Task 7: Create the external-layers TypeScript module

**Files:**
- Create: `netbox_pathways/static/netbox_pathways/src/external-layers.ts`

This module handles fetching, styling, and rendering external layers. It's imported by `pathways-map.ts`.

- [ ] **Step 1: Create `external-layers.ts`**

```typescript
/**
 * External layer rendering module.
 *
 * Fetches GeoJSON from registered external layers, applies configured
 * styles, and returns FeatureEntry objects for sidebar/popover integration.
 */

import type { FeatureEntry, GeoJSONProperties } from './types/features';

interface ExternalLayerState {
  config: ExternalLayerConfig;
  layerGroup: L.LayerGroup;
  abortController: AbortController | null;
}

const _layerStates: Map<string, ExternalLayerState> = new Map();

/** Resolve the color for a feature based on the layer style config. */
function _resolveColor(
  props: GeoJSONProperties,
  style: ExternalLayerConfig['style'],
): string {
  if (style.colorField && style.colorMap) {
    const val = String(props[style.colorField] ?? '');
    return style.colorMap[val] ?? style.defaultColor;
  }
  return style.color;
}

/** Create a Leaflet marker for a point feature. */
function _createPointMarker(
  latlng: L.LatLng,
  color: string,
  iconClass: string | null,
): L.CircleMarker {
  return L.circleMarker(latlng, {
    radius: 7,
    fillColor: color,
    color: '#fff',
    weight: 2,
    opacity: 1,
    fillOpacity: 0.85,
  });
}

/** Create a Leaflet polyline for a line feature. */
function _createLine(
  coords: L.LatLngExpression[],
  color: string,
  style: ExternalLayerConfig['style'],
): L.Polyline {
  return L.polyline(coords, {
    color,
    weight: style.weight,
    opacity: style.opacity,
    dashArray: style.dash ?? undefined,
  });
}

/** Create a Leaflet polygon for a polygon feature. */
function _createPolygon(
  coords: L.LatLngExpression[][],
  color: string,
  style: ExternalLayerConfig['style'],
): L.Polygon {
  return L.polygon(coords, {
    color,
    fillColor: color,
    fillOpacity: 0.2,
    weight: style.weight,
    opacity: style.opacity,
    dashArray: style.dash ?? undefined,
  });
}

/**
 * Initialize layer groups for all external layers.
 * Returns a map of layer name → L.LayerGroup for the layer control.
 */
export function initExternalLayers(
  configs: ExternalLayerConfig[],
  map: L.Map,
): Map<string, L.LayerGroup> {
  _layerStates.clear();
  const groups = new Map<string, L.LayerGroup>();

  // Sort by sortOrder for consistent z-ordering
  const sorted = [...configs].sort((a, b) => a.sortOrder - b.sortOrder);

  for (const cfg of sorted) {
    const group = L.layerGroup();
    _layerStates.set(cfg.name, {
      config: cfg,
      layerGroup: group,
      abortController: null,
    });
    groups.set(cfg.name, group);

    if (cfg.defaultVisible) {
      group.addTo(map);
    }
  }
  return groups;
}

/**
 * Fetch and render features for all visible external layers.
 * Returns FeatureEntry[] for sidebar integration.
 *
 * @param bbox - "W,S,E,N" string
 * @param zoom - current zoom level
 * @param visibleLayers - set of layer names currently toggled on
 * @param onFeature - callback for each created feature (for sidebar/popover wiring)
 */
export async function loadExternalLayers(
  bbox: string,
  zoom: number,
  visibleLayers: Set<string>,
  onFeature: (entry: FeatureEntry, config: ExternalLayerConfig) => void,
): Promise<FeatureEntry[]> {
  const allEntries: FeatureEntry[] = [];
  const fetchPromises: Promise<void>[] = [];

  for (const [name, state] of _layerStates) {
    if (!visibleLayers.has(name)) continue;
    if (zoom < state.config.minZoom) continue;
    if (state.config.maxZoom !== null && zoom > state.config.maxZoom) continue;

    // Abort any in-flight request for this layer
    if (state.abortController) {
      state.abortController.abort();
    }
    state.abortController = new AbortController();

    const promise = _fetchLayer(state, bbox, zoom, allEntries, onFeature);
    fetchPromises.push(promise);
  }

  await Promise.allSettled(fetchPromises);
  return allEntries;
}

async function _fetchLayer(
  state: ExternalLayerState,
  bbox: string,
  zoom: number,
  entries: FeatureEntry[],
  onFeature: (entry: FeatureEntry, config: ExternalLayerConfig) => void,
): Promise<void> {
  const { config, layerGroup, abortController } = state;
  const sep = config.url.includes('?') ? '&' : '?';
  const url = `${config.url}${sep}format=json&bbox=${bbox}&zoom=${zoom}`;

  // Read CSRF token from cookie
  const csrfMatch = document.cookie.match(/csrftoken=([^;]+)/);
  const headers: Record<string, string> = {
    Accept: 'application/json',
  };
  if (csrfMatch) {
    headers['X-CSRFToken'] = csrfMatch[1];
  }

  try {
    const resp = await fetch(url, {
      headers,
      signal: abortController?.signal,
    });
    if (!resp.ok) {
      console.warn(`External layer '${config.name}' fetch failed: ${resp.status}`);
      return;
    }
    const data = await resp.json() as GeoJSON.FeatureCollection;
    layerGroup.clearLayers();

    for (const feature of data.features) {
      if (!feature.geometry) continue;
      const props = (feature.properties ?? {}) as GeoJSONProperties;
      // Copy top-level feature.id to properties if not already present
      if (feature.id != null && props.id == null) {
        props.id = feature.id as number;
      }
      const color = _resolveColor(props, config.style);
      let layer: L.Layer | null = null;
      let latlng: L.LatLng;

      if (feature.geometry.type === 'Point') {
        const [lng, lat] = feature.geometry.coordinates as [number, number];
        latlng = L.latLng(lat, lng);
        layer = _createPointMarker(latlng, color, config.style.icon);
      } else if (
        feature.geometry.type === 'LineString' ||
        feature.geometry.type === 'MultiLineString'
      ) {
        const coords = (feature.geometry as GeoJSON.LineString).coordinates.map(
          (c: number[]) => L.latLng(c[1], c[0]),
        );
        const line = _createLine(coords, color, config.style);
        latlng = line.getBounds().getCenter();
        layer = line;
      } else if (
        feature.geometry.type === 'Polygon' ||
        feature.geometry.type === 'MultiPolygon'
      ) {
        const rings = (feature.geometry as GeoJSON.Polygon).coordinates.map(
          (ring: number[][]) => ring.map((c: number[]) => L.latLng(c[1], c[0])),
        );
        const poly = _createPolygon(rings, color, config.style);
        latlng = poly.getBounds().getCenter();
        layer = poly;
      }

      if (layer) {
        layerGroup.addLayer(layer);
        const entry: FeatureEntry = {
          props: { ...props, name: props.name ?? `${config.label} #${props.id}` },
          featureType: config.name,
          layer,
          latlng: latlng!,
        };
        entries.push(entry);
        onFeature(entry, config);
      }
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') return;
    console.warn(`External layer '${config.name}' error:`, err);
  }
}

/** Get the ExternalLayerConfig for a layer name, if it exists. */
export function getLayerConfig(name: string): ExternalLayerConfig | undefined {
  return _layerStates.get(name)?.config;
}

/** Get all layer configs. */
export function getAllLayerConfigs(): ExternalLayerConfig[] {
  return Array.from(_layerStates.values()).map(s => s.config);
}
```

- [ ] **Step 2: Type-check**

Run: `cd /opt/netbox-pathways/netbox_pathways/static/netbox_pathways && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Add `external-layers.ts` to MODULES exclusion in `bundle.cjs`**

The module is imported by `pathways-map.ts` (not a standalone entrypoint). Add it to the `MODULES` set in `bundle.cjs` so esbuild doesn't create a separate bundle:

Change:
```javascript
const MODULES = new Set(['sidebar.ts', 'popover.ts']);
```
To:
```javascript
const MODULES = new Set(['sidebar.ts', 'popover.ts', 'external-layers.ts']);
```

- [ ] **Step 4: Type-check and build**

Run: `cd /opt/netbox-pathways/netbox_pathways/static/netbox_pathways && npx tsc --noEmit && npm run build`
Expected: No type errors, build succeeds, no `dist/external-layers.min.js` created

- [ ] **Step 5: Commit**

```bash
git add netbox_pathways/static/netbox_pathways/src/external-layers.ts netbox_pathways/static/netbox_pathways/bundle.cjs
git commit -m "feat(map): add external-layers module for fetching and rendering"
```

---

## Chunk 4: Wire External Layers into the Map

### Task 8: Integrate external layers into pathways-map.ts

**Files:**
- Modify: `netbox_pathways/static/netbox_pathways/src/pathways-map.ts`

This is the most surgical task. We need to:
1. Import the external-layers module
2. Initialize external layer groups after native layers
3. Add external layers to the layer control
4. Call `loadExternalLayers()` in the `_loadData()` cycle
5. Wire sidebar/popover for external features

- [ ] **Step 1: Add imports at top of `pathways-map.ts`**

After existing imports (sidebar, popover), add:

```typescript
import {
  initExternalLayers,
  loadExternalLayers,
  getLayerConfig,
  getAllLayerConfigs,
} from './external-layers';
```

- [ ] **Step 2: Initialize external layers after native layers**

After the native layer creation block (~line 428, after `layerNames` is built), add:

```typescript
// --- External plugin layers ---
const externalConfigs: ExternalLayerConfig[] = CFG.externalLayers ?? [];
const externalGroups = initExternalLayers(externalConfigs, map);

// Add external layers to layerNames for the layer control
for (const [name, group] of externalGroups) {
  const cfg = getLayerConfig(name);
  if (cfg) {
    layerNames[cfg.label] = group;
  }
}
```

- [ ] **Step 3: Integrate into `_loadData()` fetch cycle**

Inside `_loadData()`, after the native pathway fetches complete (~line 695), add a call to load external layers. The external features feed into the same `allFeatures` array and sidebar:

```typescript
// After native layer fetches, load external layers
const visibleExternal = new Set<string>();
for (const [name, group] of externalGroups) {
  if (map.hasLayer(group)) visibleExternal.add(name);
}

loadExternalLayers(bbox, zoom, visibleExternal, (entry, cfg) => {
  // Wire click → sidebar select
  (entry.layer as L.Layer).on('click', () => Sidebar.selectFeature(entry));
  // Wire hover → popover
  (entry.layer as L.Layer).on('mouseover', (e: L.LeafletMouseEvent) => {
    Popover.show(e.latlng, entry.props, cfg.popoverFields);
  });
  (entry.layer as L.Layer).on('mouseout', () => Popover.hide());
  Sidebar.onFeatureCreated(entry);
}).then(externalEntries => {
  allFeatures.push(...externalEntries);
  Sidebar.setFeatures(allFeatures);
  // Update stats if desired
});
```

Note: The exact integration point depends on how `allFeatures` is accumulated in the current code. The pattern is: external features go into the same array as native features, and `Sidebar.setFeatures()` is called once all layers (native + external) have loaded.

- [ ] **Step 4: Persist external layer visibility in localStorage**

The existing localStorage persistence in `_buildSidebarLayerToggles()` already uses `layerNames` keys. Since we added external layers to `layerNames`, they'll be included automatically. No additional code needed.

- [ ] **Step 5: Type-check and build**

Run: `cd /opt/netbox-pathways/netbox_pathways/static/netbox_pathways && npx tsc --noEmit && npm run build`
Expected: No type errors, build succeeds

- [ ] **Step 6: Commit**

```bash
git add netbox_pathways/static/netbox_pathways/src/pathways-map.ts
git add netbox_pathways/static/netbox_pathways/dist/
git commit -m "feat(map): wire external layers into map init and data loading"
```

---

### Task 9: Update sidebar for external layer detail panels

**Files:**
- Modify: `netbox_pathways/static/netbox_pathways/src/sidebar.ts`

- [ ] **Step 1: Add external detail rendering**

The sidebar needs to handle external features in `_fetchDetail()` and `_renderEnrichedDetail()`. For external features (where `featureType` is not a native type), use the layer config's `detail` settings.

Add this import at the top of `sidebar.ts`:

```typescript
import { getLayerConfig } from './external-layers';
import type { NATIVE_TYPES } from './types/features';
```

In `_apiUrlForFeature()` (~line 264), add a fallback for external features:

```typescript
// If not a native type, check external layer config for detail URL
const extCfg = getLayerConfig(entry.featureType);
if (extCfg?.detail?.urlTemplate) {
  return extCfg.detail.urlTemplate.replace('{id}', String(entry.props.id));
}
return '';  // no detail URL available
```

In `_renderEnrichedDetail()` (~line 461), add handling for external features:

```typescript
// Check if this is an external layer feature
const extCfg = getLayerConfig(entry.featureType);
if (extCfg?.detail) {
  const table = document.createElement('table');
  table.className = 'pw-detail-table';
  for (const fieldName of extCfg.detail.fields) {
    const val = data[fieldName];
    if (val !== undefined && val !== null) {
      _addFieldRow(table, _titleCase(fieldName.replace(/_/g, ' ')), val);
    }
  }
  container.appendChild(table);
  return;
}
```

This goes before the existing native `DETAIL_FIELDS` lookup, so external features short-circuit to their own rendering path.

- [ ] **Step 2: Update type filter pills for external layers**

In `_buildTypeFilters()` (~line 193), the existing code reads `entry.featureType` to build unique type buttons. External layers will automatically get pills because they use `config.name` as `featureType`. The pill label should use the layer's `label` instead of titlecasing the internal name.

Add a label resolver:

```typescript
function _typeLabel(featureType: string): string {
  const extCfg = getLayerConfig(featureType);
  if (extCfg) return extCfg.label;
  return _titleCase(featureType.replace(/_/g, ' '));
}
```

Use `_typeLabel(type)` instead of the existing titlecase call when rendering filter pills.

- [ ] **Step 3: Handle missing detail gracefully**

If an external layer has no `detail` config, the sidebar should show GeoJSON properties directly. In `_fetchDetail()`, if `_apiUrlForFeature()` returns empty string, render properties from `entry.props`:

```typescript
if (!url) {
  // No detail endpoint — show GeoJSON properties directly
  const table = document.createElement('table');
  table.className = 'pw-detail-table';
  for (const [key, val] of Object.entries(entry.props)) {
    if (key === 'id' || key === 'url') continue;
    _addFieldRow(table, _titleCase(key.replace(/_/g, ' ')), _resolveValue(val));
  }
  container.appendChild(table);
  return;
}
```

- [ ] **Step 4: Type-check**

Run: `cd /opt/netbox-pathways/netbox_pathways/static/netbox_pathways && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add netbox_pathways/static/netbox_pathways/src/sidebar.ts
git commit -m "feat(sidebar): support external layer detail panels and type filters"
```

---

### Task 10: Update popover for configurable fields

**Files:**
- Modify: `netbox_pathways/static/netbox_pathways/src/popover.ts`

- [ ] **Step 1: Update `Popover.show()` to accept optional `popoverFields`**

Change the `show` function signature from:
```typescript
function show(latlng: L.LatLng, props: GeoJSONProperties): void
```
to:
```typescript
function show(latlng: L.LatLng, props: GeoJSONProperties, popoverFields?: string[]): void
```

Update the content rendering inside `show()`. The existing code clears `_el.textContent = ''` then creates elements from scratch — match that pattern:

```typescript
function show(latlng: L.LatLng, props: GeoJSONProperties, popoverFields?: string[]): void {
    if (!_el) return;
    _el.textContent = '';

    // Name line
    const name = document.createElement('span');
    name.className = 'pw-popover-name';
    if (popoverFields && popoverFields.length > 0) {
        name.textContent = String(props[popoverFields[0]] ?? props.name ?? `#${props.id}`);
    } else {
        name.textContent = props.name || 'Unnamed';
    }
    _el.appendChild(name);

    // Type line
    let typeText = '';
    if (popoverFields && popoverFields.length > 1) {
        typeText = popoverFields.slice(1)
            .map(f => String(props[f] ?? ''))
            .filter(Boolean)
            .join(' / ');
    } else {
        const t = props.structure_type || props.pathway_type || '';
        typeText = t ? _titleCase(t) : '';
    }
    if (typeText) {
        const type = document.createElement('span');
        type.className = 'pw-popover-type';
        type.textContent = typeText;
        _el.appendChild(type);
    }

    _position(latlng);
    _el.style.display = '';
}
```

This replaces the entire existing `show()` function body.

- [ ] **Step 2: Update native popover calls in `pathways-map.ts`**

Existing native feature hover calls like:
```typescript
Popover.show(e.latlng, entry.props);
```
don't need to change — the `popoverFields` parameter is optional and defaults to the existing behavior.

- [ ] **Step 3: Type-check and build**

Run: `cd /opt/netbox-pathways/netbox_pathways/static/netbox_pathways && npx tsc --noEmit && npm run build`
Expected: No errors, build succeeds

- [ ] **Step 4: Commit**

```bash
git add netbox_pathways/static/netbox_pathways/src/popover.ts
git add netbox_pathways/static/netbox_pathways/dist/
git commit -m "feat(popover): support configurable popover fields for external layers"
```

---

## Chunk 5: Build, Verify, and Document

### Task 11: Full build and type-check

**Files:**
- Modify: `netbox_pathways/static/netbox_pathways/dist/*` (rebuilt)

- [ ] **Step 1: Type-check all TypeScript**

Run: `cd /opt/netbox-pathways/netbox_pathways/static/netbox_pathways && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 2: Build all bundles**

Run: `cd /opt/netbox-pathways/netbox_pathways/static/netbox_pathways && npm run build`
Expected: Build succeeds, dist/ updated

- [ ] **Step 3: Run Django system check**

Run: `cd /opt/netbox-pathways && python /opt/netbox/netbox/manage.py check --deploy 2>&1 | head -5`
Expected: System check passes (or only pre-existing warnings)

- [ ] **Step 4: Run ruff lint**

Run: `cd /opt/netbox-pathways && ruff check netbox_pathways/ tests/`
Expected: Clean

- [ ] **Step 5: Run all Python tests**

Run: `cd /opt/netbox-pathways && python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 6: Commit dist files**

```bash
git add netbox_pathways/static/netbox_pathways/dist/
git commit -m "chore(build): rebuild JS bundles with external layer support"
```


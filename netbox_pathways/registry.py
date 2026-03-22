"""Map layer registry for cross-plugin map integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest

logger = logging.getLogger(__name__)

# Maps FK target model label → geometry column (or ORM lookup path) on that model.
# Multi-hop paths (e.g. 'pathways_geometry__geometry') are valid Django ORM lookups.
SUPPORTED_GEO_MODELS: dict[str, str] = {
    'netbox_pathways.Structure': 'location',
    'netbox_pathways.SiteGeometry': 'geometry',
    'dcim.Site': 'pathways_geometry__geometry',
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
        return sorted(self._layers.values(), key=lambda lr: (lr.sort_order, lr.name))

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

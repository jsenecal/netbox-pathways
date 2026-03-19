/**
 * External layer rendering module.
 *
 * Fetches GeoJSON from registered external layers, applies configured
 * styles, and returns FeatureEntry objects for sidebar/popover integration.
 */

import type { FeatureEntry, GeoJSONProperties } from './types/features';
import type { ExternalLayerConfig } from './types/external';

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
  _iconClass: string | null,
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
 * Returns a map of layer name -> L.LayerGroup for the layer control.
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

  // Wait for all fetches; individual errors are caught inside _fetchLayer
  await Promise.all(fetchPromises.map(p => p.catch(() => {})));
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
      let latlng: L.LatLng | undefined;

      if (feature.geometry.type === 'Point') {
        const [lng, lat] = (feature.geometry as GeoJSON.Point).coordinates as [number, number];
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

      if (layer && latlng) {
        layerGroup.addLayer(layer);
        const entry: FeatureEntry = {
          props: { ...props, name: props.name ?? `${config.label} #${props.id}` },
          featureType: config.name,
          layer,
          latlng,
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

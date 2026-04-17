/**
 * Core map widget field lifecycle.
 * Replaces django-leaflet's L.FieldStore + L.GeometryField with geoman.
 *
 * Finds all .pathways-map-widget divs, creates a Leaflet map with geoman
 * draw controls, loads/saves geometry from the hidden input, and fires
 * a pathways:field-ready event when done.
 */

import { getControlOptions } from './draw-controls';

interface FieldReadyDetail {
  map: L.Map;
  drawnItems: L.FeatureGroup;
  geomType: string;
}

function initWidget(container: HTMLElement): void {
  const fieldId = container.dataset.fieldId;
  if (!fieldId) return;

  const geomType = container.dataset.geomType || 'Line String';
  const input = document.getElementById(fieldId) as HTMLInputElement | null;
  if (!input) return;

  const config = window.PATHWAYS_CONFIG || {};
  const center: [number, number] = (config.center as [number, number]) || [45.5, -73.5];
  const zoom = config.zoom ?? 10;

  // Create map
  const map = L.map(container, {
    center: L.latLng(center[0], center[1]),
    zoom: zoom,
    minZoom: config.minZoom ?? 1,
    maxZoom: config.maxZoom ?? 22,
  });

  // Add tile layers
  const baseLayers = config.baseLayers;
  if (baseLayers && baseLayers.length > 0) {
    const layerControl: Record<string, L.TileLayer> = {};
    baseLayers.forEach((bl: BaseLayerConfig, i: number) => {
      const tl = L.tileLayer(bl.url, {
        attribution: bl.attribution || '',
        maxZoom: (bl as Record<string, any>).maxZoom ?? 22,
        maxNativeZoom: bl.maxNativeZoom ?? 19,
        tileSize: bl.tileSize ?? 256,
        zoomOffset: bl.zoomOffset ?? 0,
      });
      if (i === 0) tl.addTo(map);
      layerControl[bl.name] = tl;
    });
    if (Object.keys(layerControl).length > 1) {
      L.control.layers(layerControl).addTo(map);
    }
  } else {
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 22,
      maxNativeZoom: 19,
    }).addTo(map);
  }

  // Editable layer group
  const drawnItems = L.featureGroup().addTo(map);
  const pm = (map as any).pm;
  pm.setGlobalOptions({ layerGroup: drawnItems });

  // Add geoman controls
  const controlOpts = getControlOptions(geomType);
  pm.addControls(controlOpts);

  // Load existing geometry
  let currentLayer: L.Layer | null = null;
  const existingValue = input.value.trim();
  if (existingValue) {
    try {
      const geojson = JSON.parse(existingValue);
      const layer = L.GeoJSON.geometryToLayer(geojson);
      drawnItems.addLayer(layer);
      currentLayer = layer;
      map.fitBounds(drawnItems.getBounds(), { maxZoom: 18 });
      disableDrawButtons(pm, geomType);
    } catch (e) {
      console.error('Failed to parse existing geometry:', e);
    }
  }

  // Serialize helper
  function serialize(): void {
    const layers = drawnItems.getLayers();
    if (layers.length === 0) {
      input!.value = '';
      return;
    }
    const layer = layers[0] as any;
    const geojson = layer.toGeoJSON();
    input!.value = JSON.stringify(geojson.geometry);
  }

  // Single-feature mode: on create, remove previous, disable draw buttons
  map.on('pm:create', (e: any) => {
    if (currentLayer) {
      drawnItems.removeLayer(currentLayer);
    }
    currentLayer = e.layer;
    serialize();
    disableDrawButtons(pm, geomType);

    // Listen for edits on this layer
    e.layer.on('pm:edit', () => serialize());
  });

  // On remove, re-enable draw buttons
  map.on('pm:remove', (e: any) => {
    if (e.layer === currentLayer) {
      currentLayer = null;
    }
    serialize();
    enableDrawButtons(pm, geomType);
  });

  // Edits on existing layer
  if (currentLayer) {
    (currentLayer as any).on('pm:edit', () => serialize());
  }

  // Unsaved changes warning
  let unsaved = false;
  map.on('pm:create pm:remove', () => { unsaved = true; });
  drawnItems.on('layeradd', (evt: any) => {
    evt.layer.on('pm:edit', () => { unsaved = true; });
  });
  window.addEventListener('beforeunload', (e) => {
    if (unsaved) {
      e.preventDefault();
    }
  });
  const form = container.closest('form');
  if (form) {
    form.addEventListener('submit', () => { unsaved = false; });
  }

  // Fire ready event
  container.dispatchEvent(new CustomEvent<FieldReadyDetail>('pathways:field-ready', {
    bubbles: true,
    detail: { map, drawnItems, geomType },
  }));
}

function getDrawButtonNames(geomType: string): string[] {
  const normalized = geomType.replace(/\s+/g, '').toLowerCase();
  switch (normalized) {
    case 'linestring': return ['drawPolyline'];
    case 'point': return ['drawMarker'];
    case 'geometry': return ['drawMarker', 'drawPolygon'];
    default: return ['drawPolyline'];
  }
}

function disableDrawButtons(pm: any, geomType: string): void {
  if (!pm?.Toolbar) return;
  getDrawButtonNames(geomType).forEach((btn: string) => {
    try { pm.Toolbar.setButtonDisabled(btn, true); } catch { /* ignore */ }
  });
}

function enableDrawButtons(pm: any, geomType: string): void {
  if (!pm?.Toolbar) return;
  getDrawButtonNames(geomType).forEach((btn: string) => {
    try { pm.Toolbar.setButtonDisabled(btn, false); } catch { /* ignore */ }
  });
}

// Initialize all widgets when DOM is ready
function initAll(): void {
  document.querySelectorAll<HTMLElement>('.pathways-map-widget').forEach(initWidget);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAll);
} else {
  initAll();
}

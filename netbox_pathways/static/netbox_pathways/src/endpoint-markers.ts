/**
 * Locked endpoint markers for pathway edit forms.
 *
 * Reads structure geometry from a <script type="application/json"> element
 * injected by PathwaysMapWidget, draws non-editable markers on the map,
 * and snaps drawn path endpoints to structure geometry.
 *
 * In straight mode (aerial spans) the line is always the two landings: no
 * vertices can be added or removed, a point structure pins its end, and an
 * end on a polygon structure slides along the boundary. The server applies
 * the same rules; this only keeps the editor honest.
 */

import { esc } from './map-utils';

interface EndpointData {
  start?: GeoJSON.Geometry;
  end?: GeoJSON.Geometry;
  start_name?: string;
  end_name?: string;
  straight?: boolean;
}

type LatLngTuple = [number, number];

interface FieldReadyDetail {
  map: L.Map;
  drawnItems: L.FeatureGroup;
  geomType: string;
}

const MARKER_STYLE: L.CircleMarkerOptions = {
  radius: 8,
  color: '#ff6b35',
  fillColor: '#ff6b35',
  fillOpacity: 0.5,
  weight: 2,
  interactive: false,
};

const POLYGON_STYLE: L.PathOptions = {
  color: '#ff6b35',
  fillColor: '#ff6b35',
  fillOpacity: 0.1,
  weight: 2,
  dashArray: '6 4',
  interactive: false,
};

function getEndpointData(fieldId: string): EndpointData | null {
  const el = document.getElementById(fieldId + '-endpoints');
  if (!el) return null;
  try {
    return JSON.parse(el.textContent || '');
  } catch {
    return null;
  }
}

function addLabel(layer: L.Layer, name: string): void {
  layer.bindTooltip(esc(name), {
    permanent: true,
    direction: 'right',
    offset: L.point ? L.point(MARKER_STYLE.radius! + 2, 0) : undefined,
    className: 'pw-line-label pw-ref-label',
  });
}

export function addLockedGeometry(map: L.Map, geojson: GeoJSON.Geometry, name?: string): void {
  let layer: L.Layer | null = null;
  if (geojson.type === 'Point') {
    const [lng, lat] = geojson.coordinates as [number, number];
    layer = L.circleMarker([lat, lng], MARKER_STYLE).addTo(map);
  } else if (geojson.type === 'Polygon') {
    const coords = (geojson.coordinates as number[][][])[0].map(
      (c) => [c[1], c[0]] as [number, number],
    );
    layer = L.polygon(coords, POLYGON_STYLE).addTo(map);
  }
  if (layer && name) addLabel(layer, name);
}

function nearestPointOnSegment(
  a: [number, number], b: [number, number], p: [number, number],
): [number, number] {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  if (dx === 0 && dy === 0) return a;
  let t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy);
  t = Math.max(0, Math.min(1, t));
  return [a[0] + t * dx, a[1] + t * dy];
}

function nearestPointOnRing(
  ring: [number, number][], point: [number, number],
): [number, number] {
  let bestDist = Infinity, bestPoint: [number, number] = ring[0];
  for (let i = 0; i < ring.length - 1; i++) {
    const nearest = nearestPointOnSegment(ring[i], ring[i + 1], point);
    const dx = nearest[0] - point[0], dy = nearest[1] - point[1];
    const dist = dx * dx + dy * dy;
    if (dist < bestDist) { bestDist = dist; bestPoint = nearest; }
  }
  return bestPoint;
}

function getSnapTarget(geojson: GeoJSON.Geometry, latlng: LatLngTuple): LatLngTuple | null {
  if (geojson.type === 'Point') {
    const [lng, lat] = geojson.coordinates as [number, number];
    return [lat, lng];
  }
  if (geojson.type === 'Polygon') {
    const ring = (geojson.coordinates as number[][][])[0].map(
      (c) => [c[1], c[0]] as [number, number],
    );
    return nearestPointOnRing(ring, latlng);
  }
  return null;
}

/** Snap a drawn line's ends to its endpoint structures; collapse it when straight. */
export function fitPath(coords: LatLngTuple[], data: EndpointData, straight: boolean): LatLngTuple[] {
  const first = coords[0];
  const last = coords[coords.length - 1];
  const start = (data.start && getSnapTarget(data.start, first)) || first;
  const end = (data.end && getSnapTarget(data.end, last)) || last;
  return straight ? [start, end] : [start, ...coords.slice(1, -1), end];
}

function snapPath(drawnItems: L.FeatureGroup, data: EndpointData, fieldId: string): void {
  const layers = drawnItems.getLayers();
  if (layers.length === 0) return;
  const polyline = layers[0] as L.Polyline;
  if (!polyline.getLatLngs) return;
  const latLngs = polyline.getLatLngs() as L.LatLng[];
  if (latLngs.length < 2) return;

  const fitted = fitPath(latLngs.map((ll) => [ll.lat, ll.lng] as LatLngTuple), data, !!data.straight);
  polyline.setLatLngs(fitted.map(([lat, lng]) => L.latLng(lat, lng)));
  const input = document.getElementById(fieldId) as HTMLInputElement;
  if (input) {
    const geojson = (polyline as any).toGeoJSON();
    input.value = JSON.stringify(geojson.geometry);
  }
}

// Listen for pathways:field-ready on any widget
document.addEventListener('pathways:field-ready', function (e: Event) {
  const detail = (e as CustomEvent<FieldReadyDetail>).detail;
  if (!detail) return;
  const { map, drawnItems, geomType } = detail;

  // Only snap for LineString geometry
  const normalized = geomType.replace(/\s+/g, '').toLowerCase();
  if (normalized !== 'linestring') return;

  // Find the field ID from the widget container
  const container = map.getContainer();
  const fieldId = container.dataset.fieldId;
  if (!fieldId) return;

  const data = getEndpointData(fieldId);
  if (!data) return;

  // Draw locked markers, labeled like the reference-layer structures
  if (data.start) addLockedGeometry(map, data.start, data.start_name);
  if (data.end) addLockedGeometry(map, data.end, data.end_name);

  // Snap existing geometry
  snapPath(drawnItems, data, fieldId);

  // Snap on new draws
  map.on('pm:create', () => snapPath(drawnItems, data, fieldId));

  // Snap on edits, for the loaded geometry and for layers added later
  const arm = (layer: any): void => {
    if (data.straight) {
      // Hide the midpoint handles (no new vertices) and block vertex removal.
      layer.pm?.setOptions({ hideMiddleMarkers: true, preventMarkerRemoval: true });
    }
    layer.on('pm:edit', () => snapPath(drawnItems, data, fieldId));
  };
  drawnItems.eachLayer(arm);
  drawnItems.on('layeradd', (evt: any) => arm(evt.layer));
});

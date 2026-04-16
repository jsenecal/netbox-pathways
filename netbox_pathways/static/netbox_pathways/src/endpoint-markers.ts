/**
 * Locked endpoint markers for pathway edit forms.
 *
 * Reads structure geometry from a <script type="application/json"> element
 * injected by PathwaysLeafletWidget.render(), draws non-editable markers
 * on the map, and snaps drawn path endpoints to structure geometry.
 */

interface EndpointData {
  start?: GeoJSON.Geometry;
  end?: GeoJSON.Geometry;
}

interface LoadFieldEvent {
  field: {
    options: { fieldid: string };
    drawnItems: L.LayerGroup;
    store: { save: (layer: L.LayerGroup) => void };
    _drawControl?: Record<string, any>;
  };
}

(function () {
  'use strict';

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

  function addLockedGeometry(
    map: L.Map,
    geojson: GeoJSON.Geometry,
  ): void {
    if (geojson.type === 'Point') {
      const [lng, lat] = geojson.coordinates as [number, number];
      L.circleMarker([lat, lng], MARKER_STYLE).addTo(map);
    } else if (geojson.type === 'Polygon') {
      const coords = (geojson.coordinates as number[][][])[0].map(
        (c) => [c[1], c[0]] as [number, number],
      );
      L.polygon(coords, POLYGON_STYLE).addTo(map);
    }
  }

  function nearestPointOnRing(
    ring: [number, number][],
    point: [number, number],
  ): [number, number] {
    let bestDist = Infinity;
    let bestPoint: [number, number] = ring[0];

    for (let i = 0; i < ring.length - 1; i++) {
      const a = ring[i];
      const b = ring[i + 1];
      const nearest = nearestPointOnSegment(a, b, point);
      const dx = nearest[0] - point[0];
      const dy = nearest[1] - point[1];
      const dist = dx * dx + dy * dy;
      if (dist < bestDist) {
        bestDist = dist;
        bestPoint = nearest;
      }
    }
    return bestPoint;
  }

  function nearestPointOnSegment(
    a: [number, number],
    b: [number, number],
    p: [number, number],
  ): [number, number] {
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    if (dx === 0 && dy === 0) return a;
    let t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy);
    t = Math.max(0, Math.min(1, t));
    return [a[0] + t * dx, a[1] + t * dy];
  }

  function getSnapTarget(
    geojson: GeoJSON.Geometry,
    currentLatLng: L.LatLng,
  ): [number, number] | null {
    if (geojson.type === 'Point') {
      const [lng, lat] = geojson.coordinates as [number, number];
      return [lat, lng];
    }
    if (geojson.type === 'Polygon') {
      const ring = (geojson.coordinates as number[][][])[0].map(
        (c) => [c[1], c[0]] as [number, number],
      );
      return nearestPointOnRing(ring, [currentLatLng.lat, currentLatLng.lng]);
    }
    return null;
  }

  function snapDrawnPath(
    field: LoadFieldEvent['field'],
    data: EndpointData,
  ): void {
    const layers = (field.drawnItems as any).getLayers() as L.Layer[];
    if (layers.length === 0) return;

    const polyline = layers[0] as L.Polyline;
    if (!polyline.getLatLngs) return;

    const latLngs = polyline.getLatLngs() as L.LatLng[];
    if (latLngs.length < 2) return;
    let changed = false;

    if (data.start) {
      const target = getSnapTarget(data.start, latLngs[0]);
      if (target) {
        latLngs[0] = L.latLng(target[0], target[1]);
        changed = true;
      }
    }

    if (data.end) {
      const last = latLngs.length - 1;
      const target = getSnapTarget(data.end, latLngs[last]);
      if (target) {
        latLngs[last] = L.latLng(target[0], target[1]);
        changed = true;
      }
    }

    if (changed) {
      polyline.setLatLngs(latLngs);
      field.store.save(field.drawnItems as any);
    }
  }

  window.addEventListener('map:init', function (e: Event) {
    const detail = (e as CustomEvent).detail;
    const map: L.Map | undefined = detail?.map;
    if (!map) return;

    map.on('map:loadfield', function (evt: unknown) {
      const loadEvt = evt as LoadFieldEvent;
      const fieldId = loadEvt.field?.options?.fieldid;
      if (!fieldId) return;

      const data = getEndpointData(fieldId);
      if (!data) return;

      // Draw locked markers
      if (data.start) addLockedGeometry(map, data.start);
      if (data.end) addLockedGeometry(map, data.end);

      // Snap on draw events
      map.on('draw:created draw:edited', function () {
        snapDrawnPath(loadEvt.field, data);
      });
    });
  });
})();

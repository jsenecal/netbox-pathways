/**
 * Read-only nearby-structures reference layer for the map edit widget.
 *
 * Listens for pathways:field-ready (fired by pathways-field.ts), adds a
 * toggle button to the in-map helper area, and when enabled fetches the
 * structures in the current viewport from the GeoJSON API and draws them
 * as non-interactive markers. Pure context: the markers never intercept
 * clicks meant for the draw tools and nothing snaps to them. See issue #83.
 */

import { esc, structureIcon } from './map-utils';

export const MIN_REF_ZOOM = 13;
export const LABEL_ZOOM = 17;

const PREF_KEY = 'netbox-pathways:widget-ref-structures';
const COORD_EPSILON = 1e-7;  // ~1 cm in degrees; endpoint/API floats may differ in formatting
const MARKER_SIZE = 16;

// ---------------------------------------------------------------------------
// Toggle preference
// ---------------------------------------------------------------------------

export function isRefEnabled(): boolean {
    try {
        return localStorage.getItem(PREF_KEY) !== '0';
    } catch {
        return true;
    }
}

export function setRefEnabled(on: boolean): void {
    try {
        localStorage.setItem(PREF_KEY, on ? '1' : '0');
    } catch { /* ignore */ }
}

// ---------------------------------------------------------------------------
// Fetch URL
// ---------------------------------------------------------------------------

/** apiBase is read lazily -- PATHWAYS_CONFIG is injected after this bundle loads. */
function apiBase(): string {
    return window.PATHWAYS_CONFIG?.apiBase || '/api/plugins/pathways/geo/';
}

export function buildRefUrl(base: string, bbox: string, zoom: number): string {
    return base + 'structures/?format=json&bbox=' + bbox + '&zoom=' + zoom;
}

// ---------------------------------------------------------------------------
// Endpoint exclusion
// ---------------------------------------------------------------------------

interface EndpointData {
    start?: GeoJSON.Geometry;
    end?: GeoJSON.Geometry;
}

function getEndpointData(fieldId: string): EndpointData | null {
    const el = document.getElementById(fieldId + '-endpoints');
    if (!el) return null;
    try {
        return JSON.parse(el.textContent || '') as EndpointData;
    } catch {
        return null;
    }
}

/** Reference features the widget must not draw. */
export interface RefExclusions {
    /** Coordinates of locked endpoint markers, matched within COORD_EPSILON. */
    points?: GeoJSON.Position[];
    /** Structure PKs, as strings; matched wherever the feature now sits. */
    ids?: string[];
}

/**
 * Point coordinates of the pathway's own locked endpoint markers; reference
 * markers at these spots are skipped so the locked markers stay visible.
 */
export function extractExcludePoints(data: EndpointData | null): GeoJSON.Position[] {
    if (!data) return [];
    const points: GeoJSON.Position[] = [];
    for (const geom of [data.start, data.end]) {
        if (geom && geom.type === 'Point') {
            points.push(geom.coordinates as GeoJSON.Position);
        }
    }
    return points;
}

/**
 * Everything the widget container says to leave out: the object being edited
 * (data-ref-exclude-id) plus any locked endpoint markers.
 *
 * On a Structure form the record's own saved point comes back in the viewport
 * fetch, so without the id exclusion a faded read-only copy sits under the
 * editable marker -- and stays behind as a ghost once the marker is dragged.
 */
export function readExclusions(container: HTMLElement): RefExclusions {
    const fieldId = container.dataset.fieldId;
    const excludeId = container.dataset.refExcludeId;
    return {
        points: fieldId ? extractExcludePoints(getEndpointData(fieldId)) : [],
        ids: excludeId ? [excludeId] : [],
    };
}

function isExcludedPoint(coords: GeoJSON.Position, points: GeoJSON.Position[]): boolean {
    return points.some(
        (p) => Math.abs(p[0] - coords[0]) < COORD_EPSILON &&
               Math.abs(p[1] - coords[1]) < COORD_EPSILON,
    );
}

/** The API serializes the PK as the feature id; other layers copy it to props. */
function featureId(feature: GeoJSON.Feature, props: Record<string, unknown>): string | null {
    const id = feature.id ?? props.id;
    return id == null ? null : String(id);
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

export interface RenderOptions {
    zoom: number;
    exclude?: RefExclusions;
}

function ringCentroid(ring: GeoJSON.Position[] | undefined): GeoJSON.Position | null {
    if (!ring || ring.length < 4) return null;
    let area = 0, cx = 0, cy = 0;
    for (let i = 0; i < ring.length - 1; i++) {
        const [x0, y0] = ring[i];
        const [x1, y1] = ring[i + 1];
        const cross = x0 * y1 - x1 * y0;
        area += cross;
        cx += (x0 + x1) * cross;
        cy += (y0 + y1) * cross;
    }
    if (area === 0) {
        // Degenerate ring (zero area): fall back to the vertex average.
        const n = ring.length - 1;
        let sx = 0, sy = 0;
        for (let i = 0; i < n; i++) { sx += ring[i][0]; sy += ring[i][1]; }
        return [sx / n, sy / n];
    }
    return [cx / (3 * area), cy / (3 * area)];
}

/**
 * Map anchor for a reference feature: the point itself, or the centroid of a
 * polygon footprint. The widget draws markers, not outlines -- footprint
 * rendering belongs to the main map. Null means "cannot anchor, skip".
 */
export function featureAnchor(geometry: GeoJSON.Geometry): GeoJSON.Position | null {
    if (geometry.type === 'Point') return (geometry as GeoJSON.Point).coordinates;
    if (geometry.type === 'Polygon') {
        return ringCentroid((geometry as GeoJSON.Polygon).coordinates[0]);
    }
    if (geometry.type === 'MultiPolygon') {
        const first = (geometry as GeoJSON.MultiPolygon).coordinates[0];
        return first ? ringCentroid(first[0]) : null;
    }
    return null;
}

export function renderReferenceStructures(
    group: L.LayerGroup, data: GeoJSON.FeatureCollection, opts: RenderOptions,
): number {
    group.clearLayers();
    const excludePoints = opts.exclude?.points || [];
    const excludeIds = opts.exclude?.ids || [];
    let count = 0;
    for (const feature of data.features || []) {
        if (!feature.geometry) continue;
        const props = (feature.properties || {}) as Record<string, unknown>;
        // Server-side cluster blobs are not useful reference context.
        if (props.cluster) continue;
        const id = featureId(feature, props);
        if (id !== null && excludeIds.includes(id)) continue;
        const coords = featureAnchor(feature.geometry);
        if (!coords) continue;
        if (isExcludedPoint(coords, excludePoints)) continue;

        const marker = L.marker([coords[1], coords[0]], {
            icon: structureIcon((props.structure_type as string) || '', MARKER_SIZE),
            interactive: false,
            keyboard: false,
            opacity: 0.75,
        });
        const name = props.name as string | undefined;
        if (name && opts.zoom >= LABEL_ZOOM) {
            marker.bindTooltip(esc(name), {
                permanent: true,
                direction: 'right',
                offset: L.point ? L.point(MARKER_SIZE / 2 + 2, 0) : undefined,
                className: 'pw-line-label pw-ref-label',
            });
        }
        group.addLayer(marker);
        count++;
    }
    return count;
}

// ---------------------------------------------------------------------------
// Refresh
// ---------------------------------------------------------------------------

let _controller: AbortController | null = null;

export async function refreshReferenceLayer(
    map: L.Map, group: L.LayerGroup, exclude: RefExclusions,
): Promise<void> {
    const zoom = map.getZoom();
    if (!isRefEnabled() || zoom < MIN_REF_ZOOM) {
        if (_controller) { _controller.abort(); _controller = null; }
        group.clearLayers();
        return;
    }

    const b = map.getBounds();
    const bbox = b.getWest() + ',' + b.getSouth() + ',' + b.getEast() + ',' + b.getNorth();

    if (_controller) _controller.abort();
    const controller = typeof AbortController === 'function' ? new AbortController() : null;
    _controller = controller;

    try {
        const response = await fetch(buildRefUrl(apiBase(), bbox, zoom), {
            headers: { 'Accept': 'application/json' },
            signal: controller?.signal,
        });
        if (_controller === controller) _controller = null;
        if (!response.ok) return;
        const data = await response.json() as GeoJSON.FeatureCollection;
        renderReferenceStructures(group, data, { zoom, exclude });
    } catch {
        // Aborted or network error -- reference context is best-effort.
        if (_controller === controller) _controller = null;
    }
}

// ---------------------------------------------------------------------------
// Toggle control
// ---------------------------------------------------------------------------

export function addToggleControl(map: L.Map, onToggle: (on: boolean) => void): L.Control {
    const ToggleControl = L.Control.extend({
        options: { position: 'topleft' },

        onAdd(this: L.Control): HTMLElement {
            // Reuse the helper-bar styling from widget-controls.
            const bar = L.DomUtil.create('div', 'leaflet-bar pathways-helpers');
            const btn = L.DomUtil.create('a', 'pathways-helper-btn', bar) as HTMLAnchorElement;
            btn.href = '#';
            btn.setAttribute('role', 'button');
            L.DomUtil.create('i', 'mdi mdi-map-marker-multiple-outline', btn);

            // The layer state is sticky across page loads, so the button has
            // to say which way it is latched -- by fill, by label and to a
            // screen reader.
            function reflect(on: boolean): void {
                const label = on ? 'Hide nearby structures' : 'Show nearby structures';
                btn.classList.toggle('is-active', on);
                btn.setAttribute('aria-pressed', on ? 'true' : 'false');
                btn.title = label;
                btn.setAttribute('aria-label', label);
            }
            reflect(isRefEnabled());

            L.DomEvent.disableClickPropagation(bar);
            L.DomEvent.on(btn, 'click', (e: Event) => {
                L.DomEvent.preventDefault(e);
                const on = !isRefEnabled();
                setRefEnabled(on);
                reflect(on);
                onToggle(on);
            });
            return bar;
        },
    });
    const instance = new ToggleControl();
    instance.addTo(map);
    return instance;
}

// ---------------------------------------------------------------------------
// Widget wiring
// ---------------------------------------------------------------------------

interface FieldReadyDetail {
    map: L.Map;
}

document.addEventListener('pathways:field-ready', (e: Event) => {
    const detail = (e as CustomEvent<FieldReadyDetail>).detail;
    if (!detail) return;
    const { map } = detail;

    const container = map.getContainer();
    const exclude = readExclusions(container);

    const group = L.layerGroup().addTo(map);
    addToggleControl(map, () => { void refreshReferenceLayer(map, group, exclude); });
    map.on('moveend', () => { void refreshReferenceLayer(map, group, exclude); });
    void refreshReferenceLayer(map, group, exclude);
});

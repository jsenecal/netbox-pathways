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

function isExcluded(coords: GeoJSON.Position, exclude: GeoJSON.Position[]): boolean {
    return exclude.some(
        (p) => Math.abs(p[0] - coords[0]) < COORD_EPSILON &&
               Math.abs(p[1] - coords[1]) < COORD_EPSILON,
    );
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

export interface RenderOptions {
    zoom: number;
    exclude?: GeoJSON.Position[];
}

export function renderReferenceStructures(
    group: L.LayerGroup, data: GeoJSON.FeatureCollection, opts: RenderOptions,
): number {
    group.clearLayers();
    let count = 0;
    for (const feature of data.features || []) {
        if (!feature.geometry || feature.geometry.type !== 'Point') continue;
        const props = (feature.properties || {}) as Record<string, unknown>;
        // Server-side cluster blobs are not useful reference context.
        if (props.cluster) continue;
        const coords = (feature.geometry as GeoJSON.Point).coordinates;
        if (opts.exclude && isExcluded(coords, opts.exclude)) continue;

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
    map: L.Map, group: L.LayerGroup, exclude: GeoJSON.Position[],
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

function addToggleControl(map: L.Map, onToggle: (on: boolean) => void): void {
    const ToggleControl = L.Control.extend({
        options: { position: 'topleft' },

        onAdd(this: L.Control): HTMLElement {
            // Reuse the helper-bar styling from widget-controls.
            const bar = L.DomUtil.create('div', 'leaflet-bar pathways-helpers');
            const btn = L.DomUtil.create('a', 'pathways-helper-btn', bar) as HTMLAnchorElement;
            btn.href = '#';
            btn.title = 'Show nearby structures';
            btn.setAttribute('role', 'button');
            btn.setAttribute('aria-label', 'Show nearby structures');
            L.DomUtil.create('i', 'mdi mdi-map-marker-multiple-outline', btn);

            function reflect(on: boolean): void {
                btn.classList.toggle('is-active', on);
                btn.setAttribute('aria-pressed', on ? 'true' : 'false');
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
    new ToggleControl().addTo(map);
}

// ---------------------------------------------------------------------------
// Widget wiring
// ---------------------------------------------------------------------------

interface FieldReadyDetail {
    map: L.Map;
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

document.addEventListener('pathways:field-ready', (e: Event) => {
    const detail = (e as CustomEvent<FieldReadyDetail>).detail;
    if (!detail) return;
    const { map } = detail;

    const container = map.getContainer();
    const fieldId = container.dataset.fieldId;
    const exclude = fieldId ? extractExcludePoints(getEndpointData(fieldId)) : [];

    const group = L.layerGroup().addTo(map);
    addToggleControl(map, () => { void refreshReferenceLayer(map, group, exclude); });
    map.on('moveend', () => { void refreshReferenceLayer(map, group, exclude); });
    void refreshReferenceLayer(map, group, exclude);
});

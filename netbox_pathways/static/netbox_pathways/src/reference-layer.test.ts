/**
 * Tests for the reference-layer module (read-only nearby structures in the
 * map edit widget, issue #83).
 *
 * Strategy: stub Leaflet globals (L.marker, L.divIcon, L.layerGroup) and
 * globalThis.fetch, then test the toggle preference, URL construction,
 * rendering rules (clusters skipped, endpoint-coincident points skipped,
 * non-interactive markers, high-zoom labels) and the refresh gating.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
    MIN_REF_ZOOM,
    LABEL_ZOOM,
    isRefEnabled,
    setRefEnabled,
    buildRefUrl,
    extractExcludePoints,
    renderReferenceStructures,
    refreshReferenceLayer,
} from './reference-layer';

// ---------------------------------------------------------------------------
// Leaflet stubs
// ---------------------------------------------------------------------------

function createMockMarker() {
    return {
        _type: 'marker',
        bindTooltip: vi.fn(function (this: unknown) { return this; }),
    };
}

function createMockLayerGroup() {
    const layers: any[] = [];
    return {
        addLayer: vi.fn((l: any) => layers.push(l)),
        clearLayers: vi.fn(() => { layers.length = 0; }),
        _layers: layers,
    };
}

(globalThis as any).L = {
    marker: vi.fn((_latlng: any, _opts: any) => createMockMarker()),
    divIcon: vi.fn((opts: any) => ({ _type: 'divIcon', opts })),
    latLng: vi.fn((lat: number, lng: number) => ({ lat, lng })),
};

function createMockMap(zoom: number) {
    return {
        getZoom: vi.fn(() => zoom),
        getBounds: vi.fn(() => ({
            getWest: () => -73.6,
            getSouth: () => 45.4,
            getEast: () => -73.5,
            getNorth: () => 45.5,
        })),
    } as unknown as L.Map;
}

function featureCollection(features: GeoJSON.Feature[]): GeoJSON.FeatureCollection {
    return { type: 'FeatureCollection', features };
}

function pointFeature(
    lng: number, lat: number, props: Record<string, unknown> = {},
): GeoJSON.Feature {
    return {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [lng, lat] },
        properties: props,
    };
}

beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Toggle preference
// ---------------------------------------------------------------------------

describe('reference layer preference', () => {
    it('defaults to enabled', () => {
        expect(isRefEnabled()).toBe(true);
    });

    it('persists a disable across reads', () => {
        setRefEnabled(false);
        expect(isRefEnabled()).toBe(false);
        setRefEnabled(true);
        expect(isRefEnabled()).toBe(true);
    });
});

// ---------------------------------------------------------------------------
// URL construction
// ---------------------------------------------------------------------------

describe('buildRefUrl', () => {
    it('targets the structures endpoint with bbox and zoom', () => {
        const url = buildRefUrl('/api/plugins/pathways/geo/', '-73.6,45.4,-73.5,45.5', 15);
        expect(url).toBe(
            '/api/plugins/pathways/geo/structures/?format=json&bbox=-73.6,45.4,-73.5,45.5&zoom=15',
        );
    });
});

// ---------------------------------------------------------------------------
// Endpoint exclusion extraction
// ---------------------------------------------------------------------------

describe('extractExcludePoints', () => {
    it('collects Point endpoint coordinates and ignores polygons', () => {
        const pts = extractExcludePoints({
            start: { type: 'Point', coordinates: [-73.55, 45.45] },
            end: {
                type: 'Polygon',
                coordinates: [[[0, 0], [0, 1], [1, 1], [0, 0]]],
            },
        });
        expect(pts).toEqual([[-73.55, 45.45]]);
    });

    it('returns empty for missing data', () => {
        expect(extractExcludePoints(null)).toEqual([]);
        expect(extractExcludePoints({})).toEqual([]);
    });
});

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe('renderReferenceStructures', () => {
    it('renders point features as non-interactive markers', () => {
        const group = createMockLayerGroup();
        const data = featureCollection([
            pointFeature(-73.55, 45.45, { name: 'MH-1', structure_type: 'manhole' }),
            pointFeature(-73.56, 45.46, { name: 'P-2', structure_type: 'pole' }),
        ]);
        const count = renderReferenceStructures(group as unknown as L.LayerGroup, data, { zoom: 15 });
        expect(count).toBe(2);
        expect(group.addLayer).toHaveBeenCalledTimes(2);
        const opts = (L.marker as ReturnType<typeof vi.fn>).mock.calls[0][1];
        expect(opts.interactive).toBe(false);
        expect(opts.keyboard).toBe(false);
        expect(opts.icon).toBeTruthy();
    });

    it('clears previous markers before rendering', () => {
        const group = createMockLayerGroup();
        renderReferenceStructures(group as unknown as L.LayerGroup, featureCollection([]), { zoom: 15 });
        expect(group.clearLayers).toHaveBeenCalled();
    });

    it('skips server cluster features', () => {
        const group = createMockLayerGroup();
        const data = featureCollection([
            pointFeature(-73.55, 45.45, { cluster: true, point_count: 12 }),
            pointFeature(-73.56, 45.46, { name: 'P-2' }),
        ]);
        const count = renderReferenceStructures(group as unknown as L.LayerGroup, data, { zoom: 15 });
        expect(count).toBe(1);
    });

    it('skips structures coincident with locked endpoint markers', () => {
        const group = createMockLayerGroup();
        const data = featureCollection([
            pointFeature(-73.55, 45.45, { name: 'Start structure' }),
            pointFeature(-73.56, 45.46, { name: 'Mid pole' }),
        ]);
        const count = renderReferenceStructures(group as unknown as L.LayerGroup, data, {
            zoom: 15,
            exclude: [[-73.55000000004, 45.44999999996]],  // within epsilon
        });
        expect(count).toBe(1);
    });

    it('adds permanent name labels only at high zoom', () => {
        const group = createMockLayerGroup();
        const data = featureCollection([pointFeature(-73.55, 45.45, { name: 'P-1' })]);

        renderReferenceStructures(group as unknown as L.LayerGroup, data, { zoom: LABEL_ZOOM - 1 });
        expect(group._layers[0].bindTooltip).not.toHaveBeenCalled();

        renderReferenceStructures(group as unknown as L.LayerGroup, data, { zoom: LABEL_ZOOM });
        const marker = group._layers[0];
        expect(marker.bindTooltip).toHaveBeenCalledTimes(1);
        const [content, tooltipOpts] = marker.bindTooltip.mock.calls[0];
        expect(content).toBe('P-1');
        expect(tooltipOpts.permanent).toBe(true);
        expect(tooltipOpts.direction).toBe('right');
        expect(tooltipOpts.className).toContain('pw-ref-label');
    });
});

// ---------------------------------------------------------------------------
// Refresh gating
// ---------------------------------------------------------------------------

describe('refreshReferenceLayer', () => {
    function mockFetch(features: GeoJSON.Feature[]) {
        const fn = vi.fn(async () => ({
            ok: true,
            json: async () => featureCollection(features),
        }));
        (globalThis as any).fetch = fn;
        return fn;
    }

    it('fetches the viewport and renders when enabled at data zoom', async () => {
        const fetchFn = mockFetch([pointFeature(-73.55, 45.45, { name: 'P-1' })]);
        const group = createMockLayerGroup();
        await refreshReferenceLayer(createMockMap(15), group as unknown as L.LayerGroup, []);
        expect(fetchFn).toHaveBeenCalledTimes(1);
        const url = fetchFn.mock.calls[0][0] as string;
        expect(url).toContain('structures/?format=json&bbox=-73.6,45.4,-73.5,45.5&zoom=15');
        expect(group.addLayer).toHaveBeenCalledTimes(1);
    });

    it('does not fetch below the minimum zoom and clears the layer', async () => {
        const fetchFn = mockFetch([]);
        const group = createMockLayerGroup();
        await refreshReferenceLayer(createMockMap(MIN_REF_ZOOM - 1), group as unknown as L.LayerGroup, []);
        expect(fetchFn).not.toHaveBeenCalled();
        expect(group.clearLayers).toHaveBeenCalled();
    });

    it('does not fetch when the layer is disabled and clears it', async () => {
        setRefEnabled(false);
        const fetchFn = mockFetch([]);
        const group = createMockLayerGroup();
        await refreshReferenceLayer(createMockMap(15), group as unknown as L.LayerGroup, []);
        expect(fetchFn).not.toHaveBeenCalled();
        expect(group.clearLayers).toHaveBeenCalled();
    });

    it('swallows fetch errors and leaves the layer as-is', async () => {
        (globalThis as any).fetch = vi.fn(async () => { throw new Error('network'); });
        const group = createMockLayerGroup();
        await expect(
            refreshReferenceLayer(createMockMap(15), group as unknown as L.LayerGroup, []),
        ).resolves.toBeUndefined();
    });
});

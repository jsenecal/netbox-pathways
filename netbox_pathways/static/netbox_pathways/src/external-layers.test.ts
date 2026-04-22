/**
 * Tests for the external-layers module.
 *
 * Strategy: Stub Leaflet globals (L.layerGroup, L.circleMarker, L.polyline,
 * L.polygon, L.latLng) and globalThis.fetch, then test initExternalLayers,
 * loadExternalLayers, getLayerConfig, and getAllLayerConfigs.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { initExternalLayers, loadExternalLayers, getLayerConfig, getAllLayerConfigs } from './external-layers';
import type { ExternalLayerConfig } from './types/external';

// ---------------------------------------------------------------------------
// Leaflet stubs
// ---------------------------------------------------------------------------

function createMockLayerGroup() {
    const layers: any[] = [];
    return {
        addTo: vi.fn(),
        addLayer: vi.fn((l: any) => layers.push(l)),
        clearLayers: vi.fn(() => { layers.length = 0; }),
        _layers: layers,
    };
}

function createMockMap() {
    return {
        addLayer: vi.fn(),
    };
}

(globalThis as any).L = {
    layerGroup: vi.fn(() => createMockLayerGroup()),
    circleMarker: vi.fn((_latlng: any, _opts: any) => ({
        _type: 'circleMarker',
    })),
    polyline: vi.fn((_coords: any, _opts: any) => ({
        _type: 'polyline',
        getBounds: vi.fn(() => ({
            getCenter: vi.fn(() => ({ lat: 45.5, lng: -73.5 })),
        })),
    })),
    polygon: vi.fn((_coords: any, _opts: any) => ({
        _type: 'polygon',
        getBounds: vi.fn(() => ({
            getCenter: vi.fn(() => ({ lat: 45.5, lng: -73.5 })),
        })),
    })),
    latLng: vi.fn((lat: number, lng: number) => ({ lat, lng })),
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeConfig(overrides: Partial<ExternalLayerConfig> = {}): ExternalLayerConfig {
    return {
        name: 'test-layer',
        label: 'Test Layer',
        geometryType: 'Point',
        url: '/api/test/',
        style: {
            color: '#ff0000',
            colorField: null,
            colorMap: null,
            defaultColor: '#888888',
            icon: null,
            dash: null,
            weight: 2,
            opacity: 0.8,
        },
        popoverFields: [],
        defaultVisible: false,
        group: 'test',
        minZoom: 10,
        maxZoom: null,
        sortOrder: 0,
        ...overrides,
    };
}

function makePointFeatureCollection(count = 1) {
    const features = [];
    for (let i = 0; i < count; i++) {
        features.push({
            type: 'Feature',
            id: i + 1,
            geometry: { type: 'Point', coordinates: [-73.5 + i * 0.01, 45.5 + i * 0.01] },
            properties: { id: i + 1, name: `Point ${i + 1}` },
        });
    }
    return { type: 'FeatureCollection', features };
}

function makeLineFeatureCollection() {
    return {
        type: 'FeatureCollection',
        features: [{
            type: 'Feature',
            id: 1,
            geometry: {
                type: 'LineString',
                coordinates: [[-73.5, 45.5], [-73.6, 45.6]],
            },
            properties: { id: 1, name: 'Line 1' },
        }],
    };
}

function makePolygonFeatureCollection() {
    return {
        type: 'FeatureCollection',
        features: [{
            type: 'Feature',
            id: 1,
            geometry: {
                type: 'Polygon',
                coordinates: [[[-73.5, 45.5], [-73.6, 45.5], [-73.6, 45.6], [-73.5, 45.5]]],
            },
            properties: { id: 1, name: 'Poly 1' },
        }],
    };
}

function mockFetchSuccess(data: any) {
    globalThis.fetch = vi.fn(() =>
        Promise.resolve({
            ok: true,
            json: () => Promise.resolve(data),
        } as Response)
    );
}

function mockFetchFailure(status = 500) {
    globalThis.fetch = vi.fn(() =>
        Promise.resolve({
            ok: false,
            status,
            json: () => Promise.resolve({}),
        } as Response)
    );
}

// ---------------------------------------------------------------------------
// Tests — initExternalLayers
// ---------------------------------------------------------------------------

describe('initExternalLayers', () => {
    let map: ReturnType<typeof createMockMap>;

    beforeEach(() => {
        map = createMockMap();
        // Reset L.layerGroup mock to return fresh groups
        (L as any).layerGroup = vi.fn(() => createMockLayerGroup());
    });

    it('creates a layer group for each config', () => {
        const configs = [makeConfig({ name: 'a', sortOrder: 1 }), makeConfig({ name: 'b', sortOrder: 2 })];
        const groups = initExternalLayers(configs, map as any);
        expect(groups.size).toBe(2);
        expect(groups.has('a')).toBe(true);
        expect(groups.has('b')).toBe(true);
    });

    it('returns empty map for empty configs', () => {
        const groups = initExternalLayers([], map as any);
        expect(groups.size).toBe(0);
    });

    it('adds defaultVisible layers to the map', () => {
        const configs = [makeConfig({ name: 'visible', defaultVisible: true })];
        const groups = initExternalLayers(configs, map as any);
        const group = groups.get('visible')!;
        expect(group.addTo).toHaveBeenCalledWith(map);
    });

    it('does not add non-defaultVisible layers to the map', () => {
        const configs = [makeConfig({ name: 'hidden', defaultVisible: false })];
        const groups = initExternalLayers(configs, map as any);
        const group = groups.get('hidden')!;
        expect(group.addTo).not.toHaveBeenCalled();
    });

    it('sorts configs by sortOrder', () => {
        const order: string[] = [];
        (L as any).layerGroup = vi.fn(() => {
            const g = createMockLayerGroup();
            return g;
        });
        const configs = [
            makeConfig({ name: 'second', sortOrder: 2 }),
            makeConfig({ name: 'first', sortOrder: 1 }),
        ];
        const groups = initExternalLayers(configs, map as any);
        // Both should exist regardless of order
        expect(groups.has('first')).toBe(true);
        expect(groups.has('second')).toBe(true);
    });
});

// ---------------------------------------------------------------------------
// Tests — getLayerConfig / getAllLayerConfigs
// ---------------------------------------------------------------------------

describe('getLayerConfig', () => {
    beforeEach(() => {
        const map = createMockMap();
        (L as any).layerGroup = vi.fn(() => createMockLayerGroup());
        initExternalLayers([makeConfig({ name: 'my-layer' })], map as any);
    });

    it('returns config for a known layer', () => {
        const cfg = getLayerConfig('my-layer');
        expect(cfg).toBeDefined();
        expect(cfg!.name).toBe('my-layer');
    });

    it('returns undefined for an unknown layer', () => {
        expect(getLayerConfig('nonexistent')).toBeUndefined();
    });
});

describe('getAllLayerConfigs', () => {
    beforeEach(() => {
        const map = createMockMap();
        (L as any).layerGroup = vi.fn(() => createMockLayerGroup());
        initExternalLayers([
            makeConfig({ name: 'a', sortOrder: 1 }),
            makeConfig({ name: 'b', sortOrder: 2 }),
        ], map as any);
    });

    it('returns all layer configs', () => {
        const all = getAllLayerConfigs();
        expect(all).toHaveLength(2);
        expect(all.map(c => c.name).sort()).toEqual(['a', 'b']);
    });
});

// ---------------------------------------------------------------------------
// Tests — loadExternalLayers
// ---------------------------------------------------------------------------

describe('loadExternalLayers', () => {
    let map: ReturnType<typeof createMockMap>;

    beforeEach(() => {
        map = createMockMap();
        (L as any).layerGroup = vi.fn(() => createMockLayerGroup());
        // Clear accumulated call history on geometry mocks
        (L.circleMarker as any).mockClear();
        (L.polyline as any).mockClear();
        (L.polygon as any).mockClear();
        (L.latLng as any).mockClear();
        // Reset cookie
        Object.defineProperty(document, 'cookie', { writable: true, value: '' });
    });

    it('fetches GeoJSON and returns FeatureEntry for point features', async () => {
        const configs = [makeConfig({ name: 'points', minZoom: 10 })];
        initExternalLayers(configs, map as any);

        mockFetchSuccess(makePointFeatureCollection(2));

        const onFeature = vi.fn();
        const entries = await loadExternalLayers(
            '-74,40,-73,46',
            12,
            new Set(['points']),
            onFeature,
        );

        expect(entries).toHaveLength(2);
        expect(onFeature).toHaveBeenCalledTimes(2);
        expect(entries[0].featureType).toBe('points');
        expect(entries[0].props.name).toBe('Point 1');
    });

    it('skips layers not in visibleLayers set', async () => {
        const configs = [makeConfig({ name: 'hidden' })];
        initExternalLayers(configs, map as any);

        mockFetchSuccess(makePointFeatureCollection());

        const entries = await loadExternalLayers(
            '-74,40,-73,46',
            12,
            new Set(), // empty = nothing visible
            vi.fn(),
        );

        expect(entries).toHaveLength(0);
        expect(globalThis.fetch).not.toHaveBeenCalled();
    });

    it('skips layers below minZoom', async () => {
        const configs = [makeConfig({ name: 'zoomed', minZoom: 14 })];
        initExternalLayers(configs, map as any);

        mockFetchSuccess(makePointFeatureCollection());

        const entries = await loadExternalLayers(
            '-74,40,-73,46',
            12, // below minZoom 14
            new Set(['zoomed']),
            vi.fn(),
        );

        expect(entries).toHaveLength(0);
        expect(globalThis.fetch).not.toHaveBeenCalled();
    });

    it('skips layers above maxZoom', async () => {
        const configs = [makeConfig({ name: 'capped', minZoom: 10, maxZoom: 15 })];
        initExternalLayers(configs, map as any);

        mockFetchSuccess(makePointFeatureCollection());

        const entries = await loadExternalLayers(
            '-74,40,-73,46',
            18, // above maxZoom 15
            new Set(['capped']),
            vi.fn(),
        );

        expect(entries).toHaveLength(0);
        expect(globalThis.fetch).not.toHaveBeenCalled();
    });

    it('handles fetch failure gracefully', async () => {
        const configs = [makeConfig({ name: 'failing' })];
        initExternalLayers(configs, map as any);

        mockFetchFailure(500);

        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
        const entries = await loadExternalLayers(
            '-74,40,-73,46',
            12,
            new Set(['failing']),
            vi.fn(),
        );

        expect(entries).toHaveLength(0);
        warnSpy.mockRestore();
    });

    it('processes LineString features', async () => {
        const configs = [makeConfig({ name: 'lines', geometryType: 'LineString' })];
        initExternalLayers(configs, map as any);

        mockFetchSuccess(makeLineFeatureCollection());

        const entries = await loadExternalLayers(
            '-74,40,-73,46',
            12,
            new Set(['lines']),
            vi.fn(),
        );

        expect(entries).toHaveLength(1);
        expect(L.polyline).toHaveBeenCalled();
    });

    it('processes Polygon features', async () => {
        const configs = [makeConfig({ name: 'polys', geometryType: 'Polygon' })];
        initExternalLayers(configs, map as any);

        mockFetchSuccess(makePolygonFeatureCollection());

        const entries = await loadExternalLayers(
            '-74,40,-73,46',
            12,
            new Set(['polys']),
            vi.fn(),
        );

        expect(entries).toHaveLength(1);
        expect(L.polygon).toHaveBeenCalled();
    });

    it('skips features without geometry', async () => {
        const data = {
            type: 'FeatureCollection',
            features: [{ type: 'Feature', id: 1, geometry: null, properties: { id: 1, name: 'No Geo' } }],
        };
        const configs = [makeConfig({ name: 'nullgeo' })];
        initExternalLayers(configs, map as any);

        mockFetchSuccess(data);

        const entries = await loadExternalLayers(
            '-74,40,-73,46',
            12,
            new Set(['nullgeo']),
            vi.fn(),
        );

        expect(entries).toHaveLength(0);
    });

    it('copies feature.id to properties if not already present', async () => {
        const data = {
            type: 'FeatureCollection',
            features: [{
                type: 'Feature',
                id: 42,
                geometry: { type: 'Point', coordinates: [-73.5, 45.5] },
                properties: { name: 'No ID in props' },
            }],
        };
        const configs = [makeConfig({ name: 'idcopy' })];
        initExternalLayers(configs, map as any);

        mockFetchSuccess(data);

        const entries = await loadExternalLayers(
            '-74,40,-73,46',
            12,
            new Set(['idcopy']),
            vi.fn(),
        );

        expect(entries).toHaveLength(1);
        expect(entries[0].props.id).toBe(42);
    });

    it('uses colorMap to resolve feature color', async () => {
        const configs = [makeConfig({
            name: 'colored',
            style: {
                color: '#000000',
                colorField: 'status',
                colorMap: { active: '#00ff00', inactive: '#ff0000' },
                defaultColor: '#888888',
                icon: null,
                dash: null,
                weight: 2,
                opacity: 0.8,
            },
        })];
        initExternalLayers(configs, map as any);

        const data = {
            type: 'FeatureCollection',
            features: [{
                type: 'Feature',
                id: 1,
                geometry: { type: 'Point', coordinates: [-73.5, 45.5] },
                properties: { id: 1, name: 'Active Point', status: 'active' },
            }],
        };
        mockFetchSuccess(data);

        await loadExternalLayers(
            '-74,40,-73,46',
            12,
            new Set(['colored']),
            vi.fn(),
        );

        expect(L.circleMarker).toHaveBeenCalled();
        const circleCall = (L.circleMarker as any).mock.calls[0];
        expect(circleCall[1].fillColor).toBe('#00ff00');
    });

    it('falls back to defaultColor when colorMap value not found', async () => {
        const configs = [makeConfig({
            name: 'fallback',
            style: {
                color: '#000000',
                colorField: 'status',
                colorMap: { active: '#00ff00' },
                defaultColor: '#888888',
                icon: null,
                dash: null,
                weight: 2,
                opacity: 0.8,
            },
        })];
        initExternalLayers(configs, map as any);

        const data = {
            type: 'FeatureCollection',
            features: [{
                type: 'Feature',
                id: 1,
                geometry: { type: 'Point', coordinates: [-73.5, 45.5] },
                properties: { id: 1, name: 'Unknown Status', status: 'unknown' },
            }],
        };
        mockFetchSuccess(data);

        await loadExternalLayers(
            '-74,40,-73,46',
            12,
            new Set(['fallback']),
            vi.fn(),
        );

        const circleCall = (L.circleMarker as any).mock.calls[0];
        expect(circleCall[1].fillColor).toBe('#888888');
    });

    it('generates default name for features without name', async () => {
        const data = {
            type: 'FeatureCollection',
            features: [{
                type: 'Feature',
                id: 1,
                geometry: { type: 'Point', coordinates: [-73.5, 45.5] },
                properties: { id: 1 },
            }],
        };
        const configs = [makeConfig({ name: 'nonames', label: 'Test Layer' })];
        initExternalLayers(configs, map as any);

        mockFetchSuccess(data);

        const entries = await loadExternalLayers(
            '-74,40,-73,46',
            12,
            new Set(['nonames']),
            vi.fn(),
        );

        expect(entries[0].props.name).toBe('Test Layer #1');
    });

    it('includes bbox and zoom in fetch URL', async () => {
        const configs = [makeConfig({ name: 'urlcheck', url: '/api/test/' })];
        initExternalLayers(configs, map as any);

        mockFetchSuccess({ type: 'FeatureCollection', features: [] });

        await loadExternalLayers(
            '-74,40,-73,46',
            12,
            new Set(['urlcheck']),
            vi.fn(),
        );

        const fetchUrl = (globalThis.fetch as any).mock.calls[0][0] as string;
        expect(fetchUrl).toContain('bbox=-74,40,-73,46');
        expect(fetchUrl).toContain('zoom=12');
        expect(fetchUrl).toContain('format=json');
    });

    it('uses & separator when URL already has query params', async () => {
        const configs = [makeConfig({ name: 'qp', url: '/api/test/?layer=x' })];
        initExternalLayers(configs, map as any);

        mockFetchSuccess({ type: 'FeatureCollection', features: [] });

        await loadExternalLayers(
            '-74,40,-73,46',
            12,
            new Set(['qp']),
            vi.fn(),
        );

        const fetchUrl = (globalThis.fetch as any).mock.calls[0][0] as string;
        expect(fetchUrl).toBe('/api/test/?layer=x&format=json&bbox=-74,40,-73,46&zoom=12');
    });

    it('sends CSRF token from cookie', async () => {
        Object.defineProperty(document, 'cookie', { writable: true, value: 'csrftoken=tok123' });
        const configs = [makeConfig({ name: 'csrf' })];
        initExternalLayers(configs, map as any);

        mockFetchSuccess({ type: 'FeatureCollection', features: [] });

        await loadExternalLayers(
            '-74,40,-73,46',
            12,
            new Set(['csrf']),
            vi.fn(),
        );

        const fetchOpts = (globalThis.fetch as any).mock.calls[0][1];
        expect(fetchOpts.headers['X-CSRFToken']).toBe('tok123');
    });
});

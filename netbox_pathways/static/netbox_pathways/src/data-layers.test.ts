/**
 * Tests for the pure decision function that maps /info counts + thresholds
 * to a per-layer render decision plus a global cluster mode.
 *
 * The "structures clustered -> no supports" rule lives here: whenever
 * structures cross either threshold (client cluster or hide), all
 * non-structure layers are suppressed regardless of their own counts.
 */

import { describe, it, expect } from 'vitest';
import { decideLayerRendering } from './data-layers';
import type { MapInfo } from './data-layers';

function makeInfo(overrides: Partial<MapInfo> = {}): MapInfo {
    return {
        bbox: null,
        counts: {
            structures: 0,
            conduit_banks: 0,
            conduits: 0,
            aerial_spans: 0,
            direct_buried: 0,
            circuits: 0,
        },
        thresholds: {
            structures: { cluster: 200, hide: 5000 },
            conduit_banks: { hide: 500 },
            conduits: { hide: 500 },
            aerial_spans: { hide: 500 },
            direct_buried: { hide: 500 },
            circuits: { hide: 500 },
        },
        ...overrides,
    };
}

describe('decideLayerRendering', () => {
    it('renders everything when all counts are below threshold', () => {
        const info = makeInfo({
            counts: { structures: 50, conduit_banks: 10, conduits: 20, aerial_spans: 5, direct_buried: 0, circuits: 0 },
        });
        const d = decideLayerRendering(info, new Set(['structures', 'conduit_banks', 'conduits', 'aerial_spans']));
        expect(d.clusterMode).toBe('off');
        expect(d.layers.structures).toBe('render');
        expect(d.layers.conduit_banks).toBe('render');
        expect(d.layers.conduits).toBe('render');
        expect(d.layers.aerial_spans).toBe('render');
    });

    it('switches to client cluster mode and suppresses supports', () => {
        const info = makeInfo({
            counts: { structures: 1000, conduit_banks: 10, conduits: 20, aerial_spans: 5, direct_buried: 0, circuits: 0 },
        });
        const d = decideLayerRendering(info, new Set(['structures', 'conduit_banks', 'conduits']));
        expect(d.clusterMode).toBe('client');
        // Even though banks/conduits are well under their own hide threshold,
        // they're suppressed because structures are clustered.
        expect(d.layers.structures).toBe('render');
        expect(d.layers.conduit_banks).toBe('hide');
        expect(d.layers.conduits).toBe('hide');
    });

    it('switches to server cluster mode above the hide threshold', () => {
        const info = makeInfo({
            counts: { structures: 8000, conduit_banks: 10, conduits: 20, aerial_spans: 5, direct_buried: 0, circuits: 0 },
        });
        const d = decideLayerRendering(info, new Set(['structures', 'conduit_banks']));
        expect(d.clusterMode).toBe('server');
        expect(d.layers.structures).toBe('render');
        expect(d.layers.conduit_banks).toBe('hide');
    });

    it('hides per-layer when structures are off-cluster but support layer is over budget', () => {
        const info = makeInfo({
            counts: { structures: 50, conduit_banks: 800, conduits: 100, aerial_spans: 5, direct_buried: 0, circuits: 0 },
        });
        const d = decideLayerRendering(info, new Set(['structures', 'conduit_banks', 'conduits']));
        expect(d.clusterMode).toBe('off');
        expect(d.layers.conduit_banks).toBe('hide');
        expect(d.layers.conduits).toBe('render');
    });

    it('respects the enabled-layer set (disabled layers omitted)', () => {
        const info = makeInfo({
            counts: { structures: 50, conduit_banks: 100, conduits: 100, aerial_spans: 5, direct_buried: 0, circuits: 0 },
        });
        const d = decideLayerRendering(info, new Set(['structures']));
        expect(d.layers.structures).toBe('render');
        expect(d.layers.conduit_banks).toBeUndefined();
        expect(d.layers.conduits).toBeUndefined();
    });

    it('handles external reference-mode layers using their own threshold', () => {
        const info = makeInfo({
            counts: {
                structures: 50, conduit_banks: 10, conduits: 0, aerial_spans: 0,
                direct_buried: 0, circuits: 0,
                external: { splices: 30, otdr_traces: 1000 },
            },
            thresholds: {
                structures: { cluster: 200, hide: 5000 },
                conduit_banks: { hide: 500 },
                conduits: { hide: 500 },
                aerial_spans: { hide: 500 },
                direct_buried: { hide: 500 },
                circuits: { hide: 500 },
                external: { splices: { hide: 500 }, otdr_traces: { hide: 500 } },
            },
        });
        const d = decideLayerRendering(info, new Set(['structures', 'external:splices', 'external:otdr_traces']));
        expect(d.clusterMode).toBe('off');
        expect(d.layers['external:splices']).toBe('render');
        expect(d.layers['external:otdr_traces']).toBe('hide');
    });

    it('suppresses external layers when structures are clustered', () => {
        const info = makeInfo({
            counts: {
                structures: 1000, conduit_banks: 0, conduits: 0, aerial_spans: 0,
                direct_buried: 0, circuits: 0,
                external: { splices: 30 },
            },
            thresholds: {
                structures: { cluster: 200, hide: 5000 },
                conduit_banks: { hide: 500 },
                conduits: { hide: 500 },
                aerial_spans: { hide: 500 },
                direct_buried: { hide: 500 },
                circuits: { hide: 500 },
                external: { splices: { hide: 500 } },
            },
        });
        const d = decideLayerRendering(info, new Set(['structures', 'external:splices']));
        expect(d.clusterMode).toBe('client');
        expect(d.layers['external:splices']).toBe('hide');
    });
});

// ---------------------------------------------------------------------------
// exclude_status injection on layer / info requests (issue #68)
// ---------------------------------------------------------------------------

import { vi, beforeEach } from 'vitest';
import { fetchGeoJSON, fetchMapInfo, _resetInfoCache } from './data-layers';
import { StatusPrefs } from './status-prefs';
import { OccupancyPrefs } from './occupancy-prefs';
import { STRUCTURE_COLORS } from './map-utils';

/** Stub global fetch to record request URLs and answer 200 with `body`. */
function stubFetchCollecting(urls: string[], body?: unknown): void {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
        urls.push(url);
        return {
            ok: true,
            status: 200,
            headers: { get: () => '' },
            json: async () => body ?? { type: 'FeatureCollection', features: [] },
        };
    }));
}

describe('exclude_status request param', () => {
    let requestedUrls: string[];

    beforeEach(() => {
        localStorage.clear();
        _resetInfoCache();
        requestedUrls = [];
        stubFetchCollecting(requestedUrls);
    });

    it('fetchGeoJSON omits exclude_status while hiding is off', async () => {
        await fetchGeoJSON('conduits/', '0,0,1,1', () => {});
        expect(requestedUrls[0]).not.toContain('exclude_status');
    });

    it('fetchGeoJSON carries the inactive set when hiding is on', async () => {
        StatusPrefs.setHideInactive(true);
        await fetchGeoJSON('conduits/', '0,0,1,1', () => {});
        expect(requestedUrls[0]).toContain('exclude_status=retired%2Cabandoned');
    });

    it('fetchMapInfo carries the inactive set and stores available statuses', async () => {
        StatusPrefs.setHideInactive(true);
        StatusPrefs.setInactiveSet(['decommissioning']);
        stubFetchCollecting(requestedUrls, {
            bbox: null,
            counts: {},
            thresholds: {},
            statuses: [{ value: 'active', label: 'Active', color: 'green' }],
        });
        await fetchMapInfo('0,0,1,1', () => {});
        expect(requestedUrls[0]).toContain('exclude_status=decommissioning');
        expect(StatusPrefs.colorFor('active')).toBe('green');
    });
});

// ---------------------------------------------------------------------------
// occupied injection on layer / info requests (issue #112)
// ---------------------------------------------------------------------------

describe('occupied request param', () => {
    let requestedUrls: string[];

    beforeEach(() => {
        localStorage.clear();
        _resetInfoCache();
        requestedUrls = [];
        stubFetchCollecting(requestedUrls);
    });

    it('fetchGeoJSON omits occupied while hiding is off', async () => {
        await fetchGeoJSON('conduits/', '0,0,1,1', () => {});
        expect(requestedUrls[0]).not.toContain('occupied');
    });

    it('fetchGeoJSON carries occupied=true when hiding is on', async () => {
        OccupancyPrefs.setHideUnoccupied(true);
        await fetchGeoJSON('conduits/', '0,0,1,1', () => {});
        expect(requestedUrls[0]).toContain('occupied=true');
    });

    it('fetchMapInfo carries occupied=true when hiding is on', async () => {
        OccupancyPrefs.setHideUnoccupied(true);
        await fetchMapInfo('0,0,1,1', () => {});
        expect(requestedUrls[0]).toContain('occupied=true');
    });
});

// ---------------------------------------------------------------------------
// Structure layer options (#96): a Structure's geometry may be a polygon
// footprint, not just a point, so the layer Leaflet hands back has no
// getLatLng().
// ---------------------------------------------------------------------------

import { structureGeoJSONOptions, collapseAreasToPoints } from './data-layers';
import type { FeatureEntry } from './types/features';

function polygonFeature(): GeoJSON.Feature {
    return {
        type: 'Feature',
        id: 7,
        geometry: { type: 'Polygon', coordinates: [[[0, 0], [0, 2], [2, 2], [0, 0]]] },
        properties: { name: 'Vault 7', structure_type: 'vault' },
    } as GeoJSON.Feature;
}

/** Stand-in for the L.Polygon Leaflet builds from a Polygon feature. */
function polygonLayerStub() {
    return {
        getBounds: () => ({ getCenter: () => ({ lat: 1, lng: 1 }) }),
        setStyle: vi.fn(),
        on: vi.fn(),
    } as unknown as L.Layer;
}

describe('structureGeoJSONOptions', () => {
    it('registers a polygon structure at its bounds center', () => {
        const features: FeatureEntry[] = [];
        const opts = structureGeoJSONOptions(features, {});

        opts.onEachFeature!(polygonFeature(), polygonLayerStub());

        expect(features).toHaveLength(1);
        expect(features[0].featureType).toBe('structure');
        expect(features[0].latlng).toEqual({ lat: 1, lng: 1 });
    });

    it('copies the feature id onto the properties for polygon features', () => {
        const features: FeatureEntry[] = [];
        const opts = structureGeoJSONOptions(features, {});

        opts.onEachFeature!(polygonFeature(), polygonLayerStub());

        expect(features[0].props.id).toBe(7);
    });

    it('styles a polygon structure with its structure-type color', () => {
        const opts = structureGeoJSONOptions([], {});
        const style = (opts.style as (f?: GeoJSON.Feature) => L.PathOptions)(polygonFeature());

        expect(style.color).toBe(STRUCTURE_COLORS['vault']);
        expect(style.fillOpacity).toBeGreaterThan(0);
    });
});

describe('collapseAreasToPoints', () => {
    function collection(): GeoJSON.FeatureCollection {
        return {
            type: 'FeatureCollection',
            features: [
                polygonFeature(),
                {
                    type: 'Feature',
                    geometry: { type: 'Point', coordinates: [10, 20] },
                    properties: { name: 'MH-1', structure_type: 'manhole' },
                } as GeoJSON.Feature,
            ],
        };
    }

    it('replaces area geometry with its centroid below the footprint zoom', () => {
        const out = collapseAreasToPoints(collection(), 14, 18);

        // polygonFeature() is a triangle (0,0)-(0,2)-(2,2); true centroid, not
        // bbox center -- see featureAnchor in map-utils.ts.
        const coords = (out.features[0].geometry as GeoJSON.Point).coordinates;
        expect(coords[0]).toBeCloseTo(2 / 3);
        expect(coords[1]).toBeCloseTo(4 / 3);
        expect((out.features[0].properties as any).name).toBe('Vault 7');
    });

    it('keeps area geometry at or above the footprint zoom', () => {
        const data = collection();
        const out = collapseAreasToPoints(data, 18, 18);

        expect(out).toBe(data);
    });

    it('leaves point features alone', () => {
        const out = collapseAreasToPoints(collection(), 14, 18);

        expect(out.features[1].geometry).toEqual({ type: 'Point', coordinates: [10, 20] });
    });

    it('does not mutate the cached collection it was given', () => {
        const data = collection();
        collapseAreasToPoints(data, 14, 18);

        expect(data.features[0].geometry.type).toBe('Polygon');
    });
});

// ---------------------------------------------------------------------------
// Pathway layers draw map containers only (issues #166, #172)
// ---------------------------------------------------------------------------

import { PATHWAY_CONFIGS, loadDataLayers, serverSearch } from './data-layers';
import type { DataLayerGroups } from './data-layers';
import type { ServerSearchResult } from './types/features';

function query(url: string): URLSearchParams {
    return new URL(url, 'http://netbox.example').searchParams;
}

describe('pathway layer requests', () => {
    beforeEach(() => {
        localStorage.clear();
    });

    it('each drawn type is its own containers-only layer', () => {
        const pathwayLayers = PATHWAY_CONFIGS.filter(cfg => cfg.featureType !== 'circuit');
        expect(pathwayLayers.map(cfg => cfg.featureType)).toEqual(
            ['conduit_bank', 'conduit', 'aerial', 'direct_buried', 'submarine'],
        );
        for (const cfg of pathwayLayers) {
            const params = query(cfg.endpoint);
            expect(params.get('pathway_type')).toBe(cfg.featureType);
            expect(params.get('containers')).toBe('true');
        }
    });

    it('requests the submarine layer with containers=true', () => {
        const urls: string[] = [];
        stubFetchCollecting(urls);
        const groups = new Proxy({}, { get: () => ({ clearLayers: vi.fn() }) }) as unknown as DataLayerGroups;
        const bounds = { getWest: () => -1, getSouth: () => -1, getEast: () => 1, getNorth: () => 1 };
        const map = { getZoom: () => 15, getBounds: () => bounds, hasLayer: () => true } as unknown as L.Map;

        loadDataLayers(map, groups, { clusterMode: 'off', layers: { submarine: 'render' } }, null, {});

        expect(urls).toHaveLength(1);
        const url = new URL(urls[0], 'http://netbox.example');
        expect(url.pathname).toMatch(/\/geo\/pathways\/$/);
        expect(url.searchParams.get('pathway_type')).toBe('submarine');
        expect(url.searchParams.get('containers')).toBe('true');
        expect(url.searchParams.get('format')).toBe('json');
        expect(url.searchParams.get('bbox')).not.toBeNull();
    });
});

describe('serverSearch', () => {
    beforeEach(() => {
        vi.stubGlobal('L', { latLng: (lat: number, lng: number) => ({ lat, lng }) });
    });

    it('searches pathways as map containers and names the matching child', async () => {
        const urls: string[] = [];
        stubFetchCollecting(urls, {
            type: 'FeatureCollection',
            features: [{
                type: 'Feature', id: 7,
                geometry: { type: 'LineString', coordinates: [[0, 0], [1, 1]] },
                properties: { label: 'Bank 1', pathway_type: 'conduit_bank', search_match: 'Duct 7' },
            }],
        });
        let results: ServerSearchResult[] = [];

        await serverSearch('Duct 7', r => { results = r; });

        const pathwayUrls = urls.filter(u => u.includes('/geo/pathways/'));
        expect(pathwayUrls).toHaveLength(1);
        expect(query(pathwayUrls[0]).get('containers')).toBe('true');
        expect(query(pathwayUrls[0]).get('q')).toBe('Duct 7');
        const hit = results.find(r => r.featureType === 'conduit_bank');
        expect(hit).toMatchObject({ name: 'Bank 1', typeKey: 'conduit_bank', matchedChild: 'Duct 7' });
    });
});

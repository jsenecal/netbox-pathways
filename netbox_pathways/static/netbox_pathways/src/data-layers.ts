/**
 * GeoJSON data layer loading and viewport caching.
 *
 * Fetches structures and pathways from the GeoJSON API, manages an
 * overfetch cache for smooth panning, and renders features on the map.
 *
 * Shared between the full-page infrastructure map (pathways-map.ts)
 * and the route planner map (route-planner-map.ts).
 */

import type { FeatureEntry, FeatureType, GeoJSONProperties, PathwayStyle } from './types/features';
import {
    structureIcon as _structureIcon,
    clusterIcon as _clusterIcon,
    esc as _esc,
    getCookie as _getCookie,
    haversine as _haversine,
} from './map-utils';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const CFG: Partial<PathwaysConfig> = window.PATHWAYS_CONFIG || {};
const API_BASE: string = CFG.apiBase || '/api/plugins/pathways/geo/';

export { API_BASE };

export const MIN_DATA_ZOOM = 11;

/**
 * Zoom at or above which `/info` is skipped entirely. The viewport at this
 * zoom is small enough that hide/cluster thresholds are effectively
 * unreachable, so blocking the render on an `/info` round-trip just adds
 * latency. Overridable by server config (`PATHWAYS_CONFIG.skipInfoZoom`)
 * and by callers of `chooseLoadStrategy` for tests.
 */
export const SKIP_INFO_ZOOM: number = CFG.skipInfoZoom ?? 17;

// ---------------------------------------------------------------------------
// /info endpoint: per-layer counts + thresholds for the current viewport
// ---------------------------------------------------------------------------

export interface LayerThresholds {
    hide: number;
    cluster?: number;
}

export interface MapInfo {
    bbox: [number, number, number, number] | null;
    counts: {
        structures: number;
        conduit_banks: number;
        conduits: number;
        aerial_spans: number;
        direct_buried: number;
        circuits: number;
        external?: Record<string, number>;
    };
    thresholds: {
        structures: LayerThresholds;
        conduit_banks: LayerThresholds;
        conduits: LayerThresholds;
        aerial_spans: LayerThresholds;
        direct_buried: LayerThresholds;
        circuits: LayerThresholds;
        external?: Record<string, LayerThresholds>;
    };
}

export type ClusterMode = 'off' | 'client' | 'server';
export type LayerDecision = 'render' | 'hide';

export interface RenderingDecision {
    clusterMode: ClusterMode;
    layers: Record<string, LayerDecision>;
}

/**
 * Pure mapping from /info counts + thresholds + currently-enabled layers to
 * a per-layer render decision plus a global cluster mode.
 *
 * Rule of thumb: structures drive cluster mode. When structures are clustered
 * (client or server), every non-structure layer is hidden because the
 * supporting topology no longer makes sense at that density.
 *
 * Layer keys: native layers use their counts/thresholds keys directly
 * (e.g. ``'conduit_banks'``); external layers use ``'external:<name>'``.
 */
export function decideLayerRendering(info: MapInfo, enabled: Set<string>): RenderingDecision {
    const structuresCount = info.counts.structures;
    const sThresh = info.thresholds.structures;
    let clusterMode: ClusterMode = 'off';
    if (structuresCount > sThresh.hide) {
        clusterMode = 'server';
    } else if (sThresh.cluster != null && structuresCount > sThresh.cluster) {
        clusterMode = 'client';
    }

    const layers: Record<string, LayerDecision> = {};
    const suppress = clusterMode !== 'off';

    if (enabled.has('structures')) {
        layers.structures = 'render';
    }

    const nativeKeys: (keyof MapInfo['counts'])[] = [
        'conduit_banks', 'conduits', 'aerial_spans', 'direct_buried', 'circuits',
    ];
    for (const key of nativeKeys) {
        if (!enabled.has(key)) continue;
        if (suppress) {
            layers[key] = 'hide';
            continue;
        }
        const count = (info.counts[key] as number) ?? 0;
        const threshold = info.thresholds[key as keyof MapInfo['thresholds']] as LayerThresholds | undefined;
        layers[key] = threshold && count > threshold.hide ? 'hide' : 'render';
    }

    const extCounts = info.counts.external || {};
    const extThresholds = info.thresholds.external || {};
    for (const name of Object.keys(extCounts)) {
        const key = `external:${name}`;
        if (!enabled.has(key)) continue;
        if (suppress) {
            layers[key] = 'hide';
            continue;
        }
        const t = extThresholds[name];
        layers[key] = t && extCounts[name] > t.hide ? 'hide' : 'render';
    }

    return { clusterMode, layers };
}

/**
 * Synthetic "all enabled keys render" decision for the skip-info band.
 *
 * At these zooms we deliberately skip `/info`, so we have no counts.
 * The premise is that any viewport at that zoom holds too few features to
 * cross hide/cluster thresholds in practice; if a deployment hits that
 * edge case it can raise `PATHWAYS_CONFIG.skipInfoZoom`.
 */
export function decideSkipInfo(enabled: Set<string>): RenderingDecision {
    const layers: Record<string, LayerDecision> = {};
    for (const key of enabled) {
        layers[key] = 'render';
    }
    return { clusterMode: 'off', layers };
}

// ---------------------------------------------------------------------------
// /info fetch helper
// ---------------------------------------------------------------------------

let _infoController: AbortController | null = null;
let _lastInfoEtag = '';
let _lastInfo: MapInfo | null = null;

/** Returns the most recent /info response, or null if none cached yet. */
export function getLastInfo(): MapInfo | null {
    return _lastInfo;
}

/** Test-only: clear cached /info state so each test starts deterministically. */
export function _resetInfoCache(): void {
    if (_infoController) _infoController.abort();
    _infoController = null;
    _lastInfoEtag = '';
    _lastInfo = null;
}

/**
 * Fetch `/info` with conditional revalidation.
 *
 * `callback(info, changed)` -- `changed` is `true` when the server returned
 * fresh data (200) and `false` when it returned 304 Not Modified, in which
 * case `info` is the cached value. Callers can short-circuit on `!changed`
 * to avoid re-rendering when the previous decision is still valid.
 */
export async function fetchMapInfo(
    bbox: string,
    callback: (info: MapInfo, changed: boolean) => void,
): Promise<void> {
    if (_infoController) _infoController.abort();
    const controller = new AbortController();
    _infoController = controller;

    const url = API_BASE + 'info/?bbox=' + bbox;
    const headers: Record<string, string> = { 'Accept': 'application/json' };
    const csrfToken = _getCookie('csrftoken');
    if (csrfToken) headers['X-CSRFToken'] = csrfToken;
    if (_lastInfoEtag) headers['If-None-Match'] = _lastInfoEtag;

    try {
        const response = await fetch(url, { headers, signal: controller.signal });
        if (_infoController === controller) _infoController = null;
        if (response.status === 304 && _lastInfo) {
            callback(_lastInfo, false);
            return;
        }
        if (response.ok) {
            const data = await response.json() as MapInfo;
            _lastInfoEtag = response.headers.get('ETag') || '';
            _lastInfo = data;
            callback(data, true);
        }
    } catch {
        if (_infoController === controller) _infoController = null;
    }
}

// ---------------------------------------------------------------------------
// GeoJSON fetching with AbortController
// ---------------------------------------------------------------------------

const _inflightControllers: Record<string, AbortController> = {};

interface FetchResult {
    data: GeoJSON.FeatureCollection | null;  // null on 304
    etag: string;
}

export async function fetchGeoJSON(
    endpoint: string,
    bbox: string,
    callback: (result: FetchResult) => void,
    extraParams?: Record<string, string | number>,
    ifNoneMatch?: string,
): Promise<void> {
    // Abort any in-flight request for this endpoint
    if (_inflightControllers[endpoint]) {
        _inflightControllers[endpoint].abort();
    }

    let url = API_BASE + endpoint + '?format=json&bbox=' + bbox;
    if (extraParams) {
        for (const key in extraParams) {
            url += '&' + key + '=' + encodeURIComponent(String(extraParams[key]));
        }
    }

    const controller = new AbortController();
    _inflightControllers[endpoint] = controller;

    const headers: Record<string, string> = { 'Accept': 'application/json' };
    const csrfToken = _getCookie('csrftoken');
    if (csrfToken) headers['X-CSRFToken'] = csrfToken;
    if (ifNoneMatch) headers['If-None-Match'] = ifNoneMatch;

    try {
        const response = await fetch(url, { headers, signal: controller.signal });
        _inflightControllers[endpoint] = undefined!;
        const etag = response.headers.get('ETag') || '';
        if (response.status === 304) {
            callback({ data: null, etag });
        } else if (response.ok) {
            const data = await response.json() as GeoJSON.FeatureCollection;
            callback({ data, etag });
        }
    } catch (e) {
        _inflightControllers[endpoint] = undefined!;
        // Silently ignore AbortError and network errors
    }
}

// ---------------------------------------------------------------------------
// Server-side search
// ---------------------------------------------------------------------------

import type { ServerSearchResult } from './types/features';

let _searchController: AbortController | null = null;

export async function serverSearch(
    query: string,
    onResults: (results: ServerSearchResult[]) => void,
): Promise<void> {
    if (_searchController) _searchController.abort();
    const controller = new AbortController();
    _searchController = controller;

    const headers: Record<string, string> = { 'Accept': 'application/json' };
    const csrfToken = _getCookie('csrftoken');
    if (csrfToken) headers['X-CSRFToken'] = csrfToken;

    // Search all layer endpoints in parallel, without bbox
    const endpoints: [string, FeatureType, string][] = [
        ['structures/', 'structure', 'structure_type'],
        ['conduit-banks/', 'conduit_bank', 'pathway_type'],
        ['conduits/', 'conduit', 'pathway_type'],
        ['aerial-spans/', 'aerial', 'pathway_type'],
        ['direct-buried/', 'direct_buried', 'pathway_type'],
        ['circuits/', 'circuit', 'pathway_type'],
    ];

    const results: ServerSearchResult[] = [];

    const fetches = endpoints.map(function (cfg) {
        const [endpoint, featureType, typeField] = cfg;
        const url = API_BASE + endpoint + '?format=json&q=' + encodeURIComponent(query);
        return fetch(url, { headers, signal: controller.signal })
            .then(function (resp) { return resp.ok ? resp.json() : null; })
            .then(function (data: GeoJSON.FeatureCollection | null) {
                if (!data || !data.features) return;
                data.features.forEach(function (f: GeoJSON.Feature) {
                    if (!f.geometry) return;
                    const props = f.properties || {};
                    let latlng: L.LatLng;
                    if (f.geometry.type === 'Point') {
                        const coords = (f.geometry as GeoJSON.Point).coordinates;
                        latlng = L.latLng(coords[1], coords[0]);
                    } else if (f.geometry.type === 'LineString') {
                        const coords = (f.geometry as GeoJSON.LineString).coordinates;
                        const mid = coords[Math.floor(coords.length / 2)];
                        latlng = L.latLng(mid[1], mid[0]);
                    } else {
                        return;
                    }
                    results.push({
                        name: props.name || props.cid || 'Unnamed',
                        featureType: featureType,
                        typeKey: (props[typeField] as string) || featureType,
                        latlng: latlng,
                        url: props.url as string | undefined,
                    });
                });
            })
            .catch(function () { /* ignore aborted / failed */ });
    });

    try {
        await Promise.all(fetches);
        _searchController = null;
        onResults(results);
    } catch {
        _searchController = null;
    }
}

// ---------------------------------------------------------------------------
// Line labels
// ---------------------------------------------------------------------------

export function addLineLabels(geoJsonLayer: L.GeoJSON, layerGroup: L.LayerGroup, map: L.Map): void {
    if (map.getZoom() < 20) return;

    geoJsonLayer.eachLayer(function (layer: L.Layer) {
        const polyline = layer as L.Polyline;
        const coords = polyline.getLatLngs() as L.LatLng[];
        if (!coords || coords.length < 2) return;
        const feature = (polyline as any).feature as GeoJSON.Feature;
        const name = feature?.properties?.name as string | undefined;
        if (!name) return;

        const midIdx = Math.floor(coords.length / 2);
        const p1 = coords[midIdx - 1] || coords[0];
        const p2 = coords[midIdx];
        const midLat = (p1.lat + p2.lat) / 2;
        const midLng = (p1.lng + p2.lng) / 2;

        // Use screen pixel coordinates so the angle matches the visual line
        const px1 = map.latLngToContainerPoint(p1);
        const px2 = map.latLngToContainerPoint(p2);
        const dx = px2.x - px1.x;
        const dy = px2.y - px1.y;
        // Angle in screen space (0 deg = right, positive = clockwise)
        let angle = Math.atan2(dy, dx) * 180 / Math.PI;
        // Keep text readable (not upside-down)
        if (angle > 90) angle -= 180;
        if (angle < -90) angle += 180;

        const icon = L.divIcon({
            className: 'pw-line-label',
            html: '<div style="transform:rotate(' + angle + 'deg) translateY(-12px)">' + _esc(name) + '</div>',
            iconSize: [0, 0] as [number, number],
            iconAnchor: [0, 0] as [number, number],
        });

        layerGroup.addLayer(L.marker([midLat, midLng], { icon, interactive: false }));
    });
}

// ---------------------------------------------------------------------------
// Data layer groups
// ---------------------------------------------------------------------------

export interface DataLayerGroups {
    structures: L.LayerGroup;
    conduitBanks: L.LayerGroup;
    conduits: L.LayerGroup;
    aerialSpans: L.LayerGroup;
    directBuried: L.LayerGroup;
    circuits: L.LayerGroup;
}

export function createDataLayers(): DataLayerGroups {
    return {
        structures: L.layerGroup(),
        conduitBanks: L.layerGroup(),
        conduits: L.layerGroup(),
        aerialSpans: L.layerGroup(),
        directBuried: L.layerGroup(),
        circuits: L.layerGroup(),
    };
}

// ---------------------------------------------------------------------------
// Pathway config
// ---------------------------------------------------------------------------

/** Pathway layer descriptor.
 *
 * - ``endpoint``  -- GeoJSON endpoint path relative to API_BASE
 * - ``layerKey``  -- key into DataLayerGroups
 * - ``featureType`` -- canonical type label used by the sidebar/popover
 * - ``style``     -- Leaflet polyline style
 * - ``infoKey``   -- corresponding key in MapInfo.counts/thresholds; this is
 *                    what the gating decision uses
 */
export type PathwayInfoKey = 'conduit_banks' | 'conduits' | 'aerial_spans' | 'direct_buried' | 'circuits';

export interface PathwayConfig {
    endpoint: string;
    layerKey: keyof DataLayerGroups;
    featureType: FeatureType;
    style: PathwayStyle;
    infoKey: PathwayInfoKey;
}

export const PATHWAY_CONFIGS: PathwayConfig[] = [
    { endpoint: 'conduit-banks/', layerKey: 'conduitBanks', featureType: 'conduit_bank',
      style: { color: '#ad1457', weight: 5, opacity: 0.8, dashArray: '' }, infoKey: 'conduit_banks' },
    { endpoint: 'conduits/',      layerKey: 'conduits',     featureType: 'conduit',
      style: { color: '#f57c00', weight: 3, opacity: 0.7, dashArray: '5 5' }, infoKey: 'conduits' },
    { endpoint: 'aerial-spans/',  layerKey: 'aerialSpans',  featureType: 'aerial',
      style: { color: '#1565c0', weight: 3, opacity: 0.7, dashArray: '10 5' }, infoKey: 'aerial_spans' },
    { endpoint: 'direct-buried/', layerKey: 'directBuried', featureType: 'direct_buried',
      style: { color: '#616161', weight: 3, opacity: 0.7, dashArray: '2 4' }, infoKey: 'direct_buried' },
    { endpoint: 'circuits/',      layerKey: 'circuits',     featureType: 'circuit',
      style: { color: '#d32f2f', weight: 3, opacity: 0.8, dashArray: '8 6' }, infoKey: 'circuits' },
];

// ---------------------------------------------------------------------------
// Viewport cache
// ---------------------------------------------------------------------------

const GEO_CACHE_SIZE = 12;
const OVERFETCH = 0.5;      // fraction of viewport width/height to pad each side

interface GeoCacheEntry {
    west: number; south: number; east: number; north: number;
    zoom: number;
    extraKey: string;
    etag: string;
    data: GeoJSON.FeatureCollection;
}

const _geoCache: Record<string, GeoCacheEntry[]> = {};

/** Find a cache entry that covers a given viewport at a given zoom. */
function _findCovering(
    endpoint: string, zoom: number, extraKey: string,
    west: number, south: number, east: number, north: number,
): GeoCacheEntry | null {
    const entries = _geoCache[endpoint];
    if (!entries) return null;
    for (let i = entries.length - 1; i >= 0; i--) {
        const e = entries[i];
        if (e.zoom === zoom && e.extraKey === extraKey &&
            west >= e.west && south >= e.south &&
            east <= e.east && north <= e.north) {
            return e;
        }
    }
    return null;
}

function _storeInCache(
    endpoint: string, west: number, south: number, east: number, north: number,
    zoom: number, extraKey: string, etag: string, data: GeoJSON.FeatureCollection,
): void {
    if (!_geoCache[endpoint]) _geoCache[endpoint] = [];
    const cache = _geoCache[endpoint];
    cache.push({ west, south, east, north, zoom, extraKey, etag, data });
    if (cache.length > GEO_CACHE_SIZE) cache.shift();
}

export function cachedFetch(
    map: L.Map,
    endpoint: string,
    callback: (data: GeoJSON.FeatureCollection) => void,
    extraParams?: Record<string, string | number>,
): void {
    const b = map.getBounds();
    const west = b.getWest(), south = b.getSouth();
    const east = b.getEast(), north = b.getNorth();
    const zoom = map.getZoom();
    const extraKey = extraParams ? JSON.stringify(extraParams) : '';

    const cached = _findCovering(endpoint, zoom, extraKey, west, south, east, north);
    if (cached) {
        callback(cached.data);
        return;
    }

    // Cache miss -- expand bbox and fetch
    const dw = (east - west) * OVERFETCH;
    const dh = (north - south) * OVERFETCH;
    const fw = west - dw, fs = south - dh, fe = east + dw, fn = north + dh;
    const fetchBbox = fw + ',' + fs + ',' + fe + ',' + fn;

    fetchGeoJSON(endpoint, fetchBbox, function (result: FetchResult) {
        if (result.data) {
            _storeInCache(endpoint, fw, fs, fe, fn, zoom, extraKey, result.etag, result.data);
            callback(result.data);
        }
    }, extraParams);
}

// ---------------------------------------------------------------------------
// Neighbor preloading
// ---------------------------------------------------------------------------

let _preloadTimer: ReturnType<typeof setTimeout> | null = null;

export interface PreloadSpec {
    endpoint: string;
    extraParams?: Record<string, string | number>;
}

const MIN_PRELOAD_ZOOM = 14;  // don't preload at low zoom -- user is likely to zoom, not pan

export function preloadNeighbors(map: L.Map, specs: PreloadSpec[]): void {
    if (_preloadTimer) clearTimeout(_preloadTimer);

    const zoom = map.getZoom();
    if (zoom < MIN_PRELOAD_ZOOM) return;

    const b = map.getBounds();
    const vw = b.getEast() - b.getWest();
    const vh = b.getNorth() - b.getSouth();

    // Cardinal offsets: right, left, down, up
    const offsets: [number, number][] = [[vw, 0], [-vw, 0], [0, -vh], [0, vh]];

    // Build a queue of {endpoint, bbox} pairs, skipping already-cached regions
    const queue: { endpoint: string; bbox: string; fw: number; fs: number; fe: number; fn: number; zoom: number; extraKey: string; extraParams?: Record<string, string | number> }[] = [];
    for (const spec of specs) {
        const extraKey = spec.extraParams ? JSON.stringify(spec.extraParams) : '';
        for (const [dx, dy] of offsets) {
            const cw = b.getWest() + dx, cs = b.getSouth() + dy;
            const ce = b.getEast() + dx, cn = b.getNorth() + dy;
            if (_findCovering(spec.endpoint, zoom, extraKey, cw, cs, ce, cn)) continue;
            const dw = vw * OVERFETCH, dh = vh * OVERFETCH;
            const fw = cw - dw, fs = cs - dh, fe = ce + dw, fn = cn + dh;
            queue.push({
                endpoint: spec.endpoint,
                bbox: fw + ',' + fs + ',' + fe + ',' + fn,
                fw, fs, fe, fn, zoom, extraKey,
                extraParams: spec.extraParams,
            });
        }
    }

    // Drain the queue one at a time to avoid flooding the server
    let idx = 0;
    function _next(): void {
        if (idx >= queue.length) return;
        // Abort if the user has moved (zoom changed or panned significantly)
        if (map.getZoom() !== zoom) return;
        const q = queue[idx++];
        fetchGeoJSON(q.endpoint, q.bbox, function (result: FetchResult) {
            if (result.data) {
                _storeInCache(q.endpoint, q.fw, q.fs, q.fe, q.fn, q.zoom, q.extraKey, result.etag, result.data);
            }
            _preloadTimer = setTimeout(_next, 50);
        }, q.extraParams);
    }

    // Start after a short idle delay so visible data renders first
    _preloadTimer = setTimeout(_next, 200);
}

// ---------------------------------------------------------------------------
// Data loading callbacks
// ---------------------------------------------------------------------------

export interface LoadCallbacks {
    onFeatureClick?: (entry: FeatureEntry, e: L.LeafletMouseEvent) => void;
    onFeatureMouseOver?: (entry: FeatureEntry, e: L.LeafletMouseEvent, feature: GeoJSON.Feature) => void;
    onFeatureMouseOut?: () => void;
    onFeatureCreated?: (entry: FeatureEntry) => void;
    onStructuresLoaded?: (count: number) => void;
    onPathwayLoaded?: (data: GeoJSON.FeatureCollection) => void;
    onAllLoaded?: (allFeatures: FeatureEntry[]) => void;
}

/**
 * Load all data layers for the current viewport.
 *
 * Decision-driven: the caller supplies a ``RenderingDecision`` (from
 * /info + ``decideLayerRendering``) that says which layers to render and
 * whether to client-cluster structures. Layers marked ``'hide'`` are cleared
 * without a network call; layers not present in the decision are also
 * cleared (treated as disabled).
 *
 * The structures fetch always passes ``zoom`` so the server-side grid
 * cluster fallback still kicks in for any installation that doesn't have a
 * fresh /info result.
 */
export function loadDataLayers(
    map: L.Map,
    dataLayers: DataLayerGroups,
    decision: RenderingDecision | null,
    zoomHint: HTMLDivElement | null,
    callbacks: LoadCallbacks,
): void {
    const zoom = map.getZoom();

    if (zoom < MIN_DATA_ZOOM || decision == null) {
        dataLayers.structures.clearLayers();
        dataLayers.conduitBanks.clearLayers();
        dataLayers.conduits.clearLayers();
        dataLayers.aerialSpans.clearLayers();
        dataLayers.directBuried.clearLayers();
        dataLayers.circuits.clearLayers();
        if (zoomHint) zoomHint.style.display = zoom < MIN_DATA_ZOOM ? '' : 'none';
        if (callbacks.onAllLoaded) callbacks.onAllLoaded([]);
        return;
    }
    // From here on ``decision`` is non-null; the local alias lets nested
    // closures benefit from the narrowing.
    const live: RenderingDecision = decision;

    if (zoomHint) zoomHint.style.display = 'none';

    // Clear any pathway layer whose decision is 'hide' (or absent because
    // the toggle is off). Counts that don't make the cut never fetch.
    PATHWAY_CONFIGS.forEach(function (cfg) {
        if (live.layers[cfg.infoKey] !== 'render') {
            dataLayers[cfg.layerKey].clearLayers();
        }
    });

    const allFeatures: FeatureEntry[] = [];
    let pendingLoads = 0;
    let totalExpectedLoads = 0;

    const renderStructures = live.layers.structures === 'render' && map.hasLayer(dataLayers.structures);
    if (renderStructures) totalExpectedLoads++;

    let pendingPathway = 0;
    PATHWAY_CONFIGS.forEach(function (cfg) {
        if (live.layers[cfg.infoKey] === 'render' && map.hasLayer(dataLayers[cfg.layerKey])) {
            totalExpectedLoads++;
            pendingPathway++;
        }
    });

    function _checkAllLoaded(): void {
        pendingLoads++;
        if (pendingLoads === totalExpectedLoads) {
            if (callbacks.onAllLoaded) callbacks.onAllLoaded(allFeatures);
            // Prefetch cardinal neighbors for all active endpoints
            const specs: PreloadSpec[] = [];
            if (renderStructures) {
                specs.push({ endpoint: 'structures/', extraParams: { zoom: zoom } });
            }
            PATHWAY_CONFIGS.forEach(function (cfg) {
                if (live.layers[cfg.infoKey] === 'render' && map.hasLayer(dataLayers[cfg.layerKey])) {
                    specs.push({ endpoint: cfg.endpoint });
                }
            });
            preloadNeighbors(map, specs);
        }
    }

    function _pathwayLoaded(data: GeoJSON.FeatureCollection): void {
        if (callbacks.onPathwayLoaded) callbacks.onPathwayLoaded(data);
        pendingPathway--;
    }

    // Structures
    if (renderStructures) {
        // Client clustering is only used when the decision says 'client'; in
        // 'off' mode markers render plain, in 'server' mode the response
        // already contains pre-aggregated cluster centroids.
        const hasClusterPlugin = typeof L.markerClusterGroup === 'function';
        if (!hasClusterPlugin && live.clusterMode === 'client') {
            console.info('[pathways] MarkerCluster plugin not loaded -- client-side clustering disabled');
        }
        const useClientCluster = live.clusterMode === 'client' && hasClusterPlugin;
        const clusterGroup = useClientCluster
            ? L.markerClusterGroup({ maxClusterRadius: 35, spiderfyOnMaxZoom: true })
            : null;

        cachedFetch(map, 'structures/', function (data: GeoJSON.FeatureCollection) {
            dataLayers.structures.clearLayers();

            const isServerClustered = data.features && data.features.length > 0 &&
                (data.features[0].properties as GeoJSONProperties)?.cluster;

            if (isServerClustered) {
                let total = 0;
                data.features.forEach(function (f: GeoJSON.Feature) {
                    const props = f.properties as GeoJSONProperties;
                    const count = props.point_count || 0;
                    total += count;
                    const geom = f.geometry as GeoJSON.Point;
                    const latlng = L.latLng(geom.coordinates[1], geom.coordinates[0]);
                    const marker = L.marker(latlng, { icon: _clusterIcon(count) });
                    marker.on('click', function () {
                        const nextZoom = Math.min(map.getZoom() + 3, map.getMaxZoom());
                        map.setView(latlng, nextZoom);
                    });
                    dataLayers.structures.addLayer(marker);
                });
                if (callbacks.onStructuresLoaded) callbacks.onStructuresLoaded(total);
            } else {
                const geoLayer = L.geoJSON(data, {
                    pointToLayer: function (feature: GeoJSON.Feature, latlng: L.LatLng) {
                        return L.marker(latlng, {
                            icon: _structureIcon((feature.properties as GeoJSONProperties).structure_type || ''),
                        });
                    },
                    onEachFeature: function (feature: GeoJSON.Feature, layer: L.Layer) {
                        if (feature.id != null && (feature.properties as GeoJSONProperties).id == null) {
                            (feature.properties as GeoJSONProperties).id = feature.id as number;
                        }
                        const entry: FeatureEntry = {
                            props: feature.properties as GeoJSONProperties,
                            featureType: 'structure',
                            layer: layer,
                            latlng: (layer as L.Marker).getLatLng(),
                        };
                        allFeatures.push(entry);
                        if (callbacks.onFeatureCreated) callbacks.onFeatureCreated(entry);
                        layer.on('click', function (e: L.LeafletMouseEvent) {
                            if (callbacks.onFeatureClick) callbacks.onFeatureClick(entry, e);
                        });
                        layer.on('mouseover', function (e: L.LeafletMouseEvent) {
                            if (callbacks.onFeatureMouseOver) callbacks.onFeatureMouseOver(entry, e, feature);
                        });
                        layer.on('mouseout', function () {
                            if (callbacks.onFeatureMouseOut) callbacks.onFeatureMouseOut();
                        });
                    },
                });
                if (clusterGroup) {
                    clusterGroup.addLayers(geoLayer.getLayers());
                    dataLayers.structures.addLayer(clusterGroup);
                } else {
                    geoLayer.addTo(dataLayers.structures);
                }
                if (callbacks.onStructuresLoaded) {
                    callbacks.onStructuresLoaded(data.features ? data.features.length : 0);
                }
            }
            _checkAllLoaded();
        }, { zoom: zoom });
    }

    if (pendingPathway === 0 && callbacks.onPathwayLoaded) {
        // No pathway layers active -- signal with empty data
    }

    // Shared pathway handler factory
    function _makePathwayOpts(featureType: FeatureType, styleObj: PathwayStyle): L.GeoJSONOptions {
        return {
            style: function () { return styleObj; },
            onEachFeature: function (feature: GeoJSON.Feature, layer: L.Layer) {
                const props = feature.properties as GeoJSONProperties;
                if (feature.id != null && props.id == null) {
                    props.id = feature.id as number;
                }
                // Normalise: pathways use "label", map UI expects "name"
                if (!props.name && props.label) props.name = props.label as string;
                const entry: FeatureEntry = {
                    props: props,
                    featureType: featureType,
                    layer: layer,
                    latlng: (layer as L.Polyline).getBounds().getCenter(),
                };
                allFeatures.push(entry);
                if (callbacks.onFeatureCreated) callbacks.onFeatureCreated(entry);
                layer.on('click', function (e: L.LeafletMouseEvent) {
                    if (callbacks.onFeatureClick) callbacks.onFeatureClick(entry, e);
                });
                layer.on('mouseover', function (e: L.LeafletMouseEvent) {
                    if (callbacks.onFeatureMouseOver) callbacks.onFeatureMouseOver(entry, e, feature);
                });
                layer.on('mouseout', function () {
                    if (callbacks.onFeatureMouseOut) callbacks.onFeatureMouseOut();
                });
            },
        };
    }

    PATHWAY_CONFIGS.forEach(function (cfg) {
        const layer = dataLayers[cfg.layerKey];
        if (live.layers[cfg.infoKey] !== 'render') return;
        if (!map.hasLayer(layer)) return;
        cachedFetch(map, cfg.endpoint, function (data: GeoJSON.FeatureCollection) {
            layer.clearLayers();
            const geoLayer = L.geoJSON(data, _makePathwayOpts(cfg.featureType, cfg.style));
            geoLayer.addTo(layer);
            addLineLabels(geoLayer, layer, map);
            _pathwayLoaded(data);
            _checkAllLoaded();
        });
    });

    // If no layers active, still signal completion
    if (totalExpectedLoads === 0) {
        if (callbacks.onAllLoaded) callbacks.onAllLoaded([]);
    }
}

/**
 * Calculate total pathway length from a GeoJSON FeatureCollection.
 * Returns length in meters.
 */
export function calcPathwayLength(data: GeoJSON.FeatureCollection): number {
    let totalLength = 0;
    if (data.features) {
        data.features.forEach(function (f: GeoJSON.Feature) {
            if (f.geometry && f.geometry.type === 'LineString') {
                const coords = (f.geometry as GeoJSON.LineString).coordinates;
                for (let i = 0; i < coords.length - 1; i++) {
                    totalLength += _haversine(
                        coords[i][1], coords[i][0],
                        coords[i + 1][1], coords[i + 1][0],
                    );
                }
            }
        });
    }
    return totalLength;
}

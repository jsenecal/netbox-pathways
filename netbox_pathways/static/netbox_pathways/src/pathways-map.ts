/**
 * Full-page infrastructure map.
 *
 * Fetches structures and pathways from the GeoJSON API within the visible
 * bounding box, but only when zoomed in past a minimum threshold.
 * Re-fetches on pan/zoom with debouncing.
 *
 * Structures use server-side grid clustering at low zoom levels (11-14)
 * to avoid transferring thousands of features just for client-side clustering.
 * At zoom 15+ individual features are returned and optionally client-clustered.
 */

import { Sidebar } from './sidebar';
import { Popover } from './popover';
import type { FeatureEntry, FeatureType, GeoJSONProperties, PathwayStyle, ServerSearchResult } from './types/features';
import {
    initExternalLayers,
    loadExternalLayers,
    getLayerConfig,
} from './external-layers';
import type { ExternalLayerConfig } from './types/external';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const CFG: Partial<PathwaysConfig> = window.PATHWAYS_CONFIG || {};
const API_BASE: string = CFG.apiBase || '/api/plugins/pathways/geo/';
const MAX_NATIVE_ZOOM: number = CFG.maxNativeZoom || 19;
const MIN_DATA_ZOOM = 11;

// ---------------------------------------------------------------------------
// Color & Icon Maps
// ---------------------------------------------------------------------------

const STRUCTURE_COLORS: Record<string, string> = {
    'pole': '#2e7d32', 'manhole': '#1565c0', 'handhole': '#00838f',
    'cabinet': '#e65100', 'vault': '#6a1b9a', 'pedestal': '#f9a825',
    'building_entrance': '#c62828', 'splice_closure': '#795548',
    'tower': '#b71c1c', 'roof': '#616161', 'equipment_room': '#00796b',
    'telecom_closet': '#283593', 'riser_room': '#ad1457',
};

const STRUCTURE_SHAPES: Record<string, string> = {
    'pole':               '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/><circle cx="10" cy="10" r="2.5"/>',
    'manhole':            '<circle cx="10" cy="10" r="8"/>',
    'handhole':           '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/>',
    'cabinet':            '<rect x="2" y="2" width="16" height="16" rx="4"/>',
    'vault':              '<rect x="2" y="2" width="16" height="16" rx="2"/>',
    'pedestal':           '<rect x="3" y="3" width="14" height="14" rx="2" fill="none" stroke-width="2.5"/>',
    'building_entrance':  '<rect x="3" y="3" width="14" height="14" rx="2" fill="none" stroke-width="2.5"/><circle cx="10" cy="10" r="2.5"/>',
    'splice_closure':     '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/><circle cx="10" cy="10" r="2.5"/>',
    'tower':              '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/><line x1="10" y1="2" x2="10" y2="18" stroke-width="1.5"/><line x1="2" y1="10" x2="18" y2="10" stroke-width="1.5"/>',
    'roof':               '<polygon points="10,2 18,17 2,17"/>',
    'equipment_room':     '<rect x="3" y="3" width="14" height="14" rx="4" fill="none" stroke-width="2.5"/>',
    'telecom_closet':     '<rect x="3" y="3" width="10" height="10" rx="1" transform="rotate(45 10 10)"/>',
    'riser_room':         '<rect x="3.5" y="3.5" width="9" height="9" rx="1" fill="none" stroke-width="2.5" transform="rotate(45 10 10)"/>',
};

const PATHWAY_COLORS: Record<string, string> = {
    'conduit': '#795548', 'aerial': '#1565c0', 'direct_buried': '#616161',
    'innerduct': '#e65100', 'microduct': '#6a1b9a', 'tray': '#2e7d32',
    'raceway': '#00838f', 'submarine': '#1a237e',
};

// ---------------------------------------------------------------------------
// Marker helpers
// ---------------------------------------------------------------------------

function _structureIcon(type: string, size = 20): L.DivIcon {
    const color = STRUCTURE_COLORS[type] || '#616161';
    const shape = STRUCTURE_SHAPES[type] || '<circle cx="10" cy="10" r="8"/>';
    const isOutline = shape.includes('fill="none"');
    const half = size / 2;
    return L.divIcon({
        className: 'pw-marker',
        html: '<svg class="pw-marker-svg" viewBox="0 0 20 20" width="' + size +
              '" height="' + size + '" stroke="' + (isOutline ? color : 'white') +
              '" fill="' + color + '">' + shape + '</svg>',
        iconSize: [size, size] as [number, number],
        iconAnchor: [half, half] as [number, number],
        popupAnchor: [0, -(half + 2)] as [number, number],
    });
}

function _clusterIcon(count: number): L.DivIcon {
    let cls: string;
    let size: number;
    if (count < 10) {
        cls = 'pw-cluster-small'; size = 34;
    } else if (count < 100) {
        cls = 'pw-cluster-medium'; size = 40;
    } else {
        cls = 'pw-cluster-large'; size = 46;
    }
    return L.divIcon({
        className: 'pw-server-cluster',
        html: '<div class="pw-cluster-ring ' + cls + '" style="width:' + size +
              'px;height:' + size + 'px"><div class="pw-cluster-inner"><span>' +
              count + '</span></div></div>',
        iconSize: [size, size] as [number, number],
        iconAnchor: [size / 2, size / 2] as [number, number],
    });
}

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

function _esc(text: string): string {
    const el = document.createElement('span');
    el.textContent = text;
    return el.innerHTML;
}

function _titleCase(str: string): string {
    return (str || '').replace(/_/g, ' ').replace(/\b\w/g, function (c: string) { return c.toUpperCase(); });
}

function _getCookie(name: string): string | null {
    const value = '; ' + document.cookie;
    const parts = value.split('; ' + name + '=');
    if (parts.length === 2) return parts.pop()!.split(';').shift() || null;
    return null;
}

function _bboxParam(map: L.Map): string {
    const b = map.getBounds();
    return b.getWest() + ',' + b.getSouth() + ',' + b.getEast() + ',' + b.getNorth();
}

function _debounce(fn: () => void, delay: number): () => void {
    let timer: ReturnType<typeof setTimeout>;
    return function () {
        clearTimeout(timer);
        timer = setTimeout(fn, delay);
    };
}

function _haversine(lat1: number, lon1: number, lat2: number, lon2: number): number {
    const R = 6371000;
    const p1 = lat1 * Math.PI / 180;
    const p2 = lat2 * Math.PI / 180;
    const dp = (lat2 - lat1) * Math.PI / 180;
    const dl = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dp / 2) * Math.sin(dp / 2) +
              Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) * Math.sin(dl / 2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ---------------------------------------------------------------------------
// GeoJSON fetching with AbortController
// ---------------------------------------------------------------------------

const _inflightControllers: Record<string, AbortController> = {};

async function _fetchGeoJSON(
    endpoint: string,
    bbox: string,
    callback: (data: GeoJSON.FeatureCollection) => void,
    extraParams?: Record<string, string | number>,
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

    try {
        const response = await fetch(url, { headers, signal: controller.signal });
        _inflightControllers[endpoint] = undefined!;
        if (response.ok) {
            const data = await response.json() as GeoJSON.FeatureCollection;
            callback(data);
        }
    } catch (e) {
        _inflightControllers[endpoint] = undefined!;
        // Silently ignore AbortError and network errors
    }
}

// ---------------------------------------------------------------------------
// Server-side search (fallback when client-side sidebar filter finds nothing)
// ---------------------------------------------------------------------------

let _searchController: AbortController | null = null;

async function _serverSearch(query: string): Promise<void> {
    if (_searchController) _searchController.abort();
    const controller = new AbortController();
    _searchController = controller;

    const headers: Record<string, string> = { 'Accept': 'application/json' };
    const csrfToken = _getCookie('csrftoken');
    if (csrfToken) headers['X-CSRFToken'] = csrfToken;

    // Search all layer endpoints in parallel, without bbox
    const endpoints: [string, FeatureType, string][] = [
        ['structures/', 'structure', 'structure_type'],
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
        Sidebar.setServerResults(results);
    } catch {
        _searchController = null;
    }
}

// ---------------------------------------------------------------------------
// Line labels
// ---------------------------------------------------------------------------

function _addLineLabels(geoJsonLayer: L.GeoJSON, layerGroup: L.LayerGroup, map: L.Map): void {
    if (map.getZoom() < 15) return;

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

        const dx = p2.lng - p1.lng;
        const dy = p2.lat - p1.lat;
        let angle = Math.atan2(dy, dx) * 180 / Math.PI;
        if (angle > 90) angle -= 180;
        if (angle < -90) angle += 180;

        const icon = L.divIcon({
            className: 'pw-line-label',
            html: '<div style="transform:rotate(' + (-angle) + 'deg)">' + _esc(name) + '</div>',
            iconSize: [0, 0] as [number, number],
            iconAnchor: [0, 0] as [number, number],
        });

        layerGroup.addLayer(L.marker([midLat, midLng], { icon, interactive: false }));
    });
}

// ---------------------------------------------------------------------------
// Base layers
// ---------------------------------------------------------------------------

interface BaseLayerDef {
    name: string;
    url: string;
    attribution?: string;
    maxNativeZoom?: number;
    tileSize?: number;
    zoomOffset?: number;
}

const DEFAULT_BASE_LAYERS: BaseLayerDef[] = [
    {
        name: 'Street',
        url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        attribution: '&copy; OpenStreetMap contributors',
        maxNativeZoom: MAX_NATIVE_ZOOM,
    },
    {
        name: 'Satellite',
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attribution: 'Esri World Imagery',
        maxNativeZoom: 19,
    },
];

function _createBaseLayers(): Record<string, L.TileLayer> {
    const configured = (CFG.baseLayers || []).filter(function (c: BaseLayerConfig) { return !!c.url; });
    const configs: BaseLayerDef[] = configured.length ? configured : DEFAULT_BASE_LAYERS;
    const layers: Record<string, L.TileLayer> = {};
    configs.forEach(function (cfg: BaseLayerDef) {
        layers[cfg.name] = L.tileLayer(cfg.url, {
            attribution: cfg.attribution || '',
            maxNativeZoom: cfg.maxNativeZoom || MAX_NATIVE_ZOOM,
            maxZoom: 22,
            tileSize: cfg.tileSize || 256,
            zoomOffset: cfg.zoomOffset || 0,
        });
    });
    return layers;
}

// ---------------------------------------------------------------------------
// User-configured overlays
// ---------------------------------------------------------------------------

function _createUserOverlays(): Record<string, L.TileLayer | L.TileLayer.WMS> {
    const userOverlays = CFG.overlays || [];
    const overlays: Record<string, L.TileLayer | L.TileLayer.WMS> = {};
    userOverlays.forEach(function (cfg: OverlayConfig) {
        let layer: L.TileLayer | L.TileLayer.WMS;
        if (cfg.type === 'wms') {
            layer = L.tileLayer.wms(cfg.url, {
                layers: (cfg['layers'] as string) || '',
                format: (cfg['format'] as string) || 'image/png',
                transparent: cfg['transparent'] !== false,
                attribution: (cfg['attribution'] as string) || '',
                maxZoom: 22,
            });
        } else {
            layer = L.tileLayer(cfg.url, {
                attribution: (cfg['attribution'] as string) || '',
                maxZoom: (cfg['maxZoom'] as number) || 22,
                maxNativeZoom: (cfg['maxNativeZoom'] as number) || undefined,
            });
        }
        overlays[cfg.name] = layer;
    });
    return overlays;
}

// ---------------------------------------------------------------------------
// Zoom hint overlay
// ---------------------------------------------------------------------------

function _createZoomHint(map: L.Map): HTMLDivElement {
    const div = L.DomUtil.create('div', 'pathways-zoom-hint') as HTMLDivElement;
    div.style.cssText =
        'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);' +
        'z-index:800;padding:12px 24px;border-radius:8px;font-size:14px;' +
        'pointer-events:none;text-align:center;' +
        'background:rgba(0,0,0,0.7);color:#fff;';
    div.textContent = 'Zoom in to see infrastructure data';
    map.getContainer().appendChild(div);
    return div;
}

// ---------------------------------------------------------------------------
// Legend control
// ---------------------------------------------------------------------------

const PATHWAY_DASH: Record<string, string> = {
    'conduit': '5,5', 'aerial': '10,5', 'direct_buried': '2,4',
    'innerduct': '8,3', 'microduct': '1,3', 'tray': '',
    'raceway': '12,4', 'submarine': '6,2,2,2',
};

/**
 * Inject trusted static SVG markup into an element.
 *
 * Security: All SVG strings passed to this helper originate from compile-time
 * constants (STRUCTURE_SHAPES, PATHWAY_COLORS, PATHWAY_DASH) defined in this
 * file — no user/network input is involved. This is the same trust model as
 * _structureIcon() which also builds innerHTML from these constants.
 */
function _setStaticSvg(el: HTMLElement, svg: string): void {
    el.innerHTML = svg; // eslint-disable-line no-unsanitized/property
}

function _createLegend(map: L.Map): void {
    const LegendControl = L.Control.extend({
        options: { position: 'bottomleft' },
        onAdd: function () {
            const container = L.DomUtil.create('div', 'pw-legend leaflet-bar');
            L.DomEvent.disableClickPropagation(container);
            L.DomEvent.disableScrollPropagation(container);

            // Header
            const header = L.DomUtil.create('div', 'pw-legend-header', container);
            const chevron = document.createElement('i');
            chevron.className = 'mdi mdi-chevron-down';
            header.appendChild(chevron);
            const titleSpan = document.createElement('span');
            titleSpan.textContent = 'Legend';
            header.appendChild(titleSpan);

            // Body
            const body = L.DomUtil.create('div', 'pw-legend-body', container);

            // Structures section
            const structSec = L.DomUtil.create('div', 'pw-legend-section', body);
            const structTitle = L.DomUtil.create('div', 'pw-legend-section-title', structSec);
            structTitle.textContent = 'Structures';

            const structTypes = ['pole', 'manhole', 'handhole', 'cabinet', 'vault',
                'pedestal', 'building_entrance', 'splice_closure', 'tower',
                'equipment_room', 'telecom_closet', 'riser_room'];
            for (let i = 0; i < structTypes.length; i++) {
                const stype = structTypes[i];
                const color = STRUCTURE_COLORS[stype] || '#616161';
                const shape = STRUCTURE_SHAPES[stype] || '<circle cx="10" cy="10" r="8"/>';
                const isOutline = shape.includes('fill="none"');
                const item = L.DomUtil.create('div', 'pw-legend-item', structSec);
                const swatch = L.DomUtil.create('span', 'pw-legend-swatch', item);
                _setStaticSvg(swatch,
                    '<svg viewBox="0 0 20 20" width="14" height="14" ' +
                    'stroke="' + (isOutline ? color : 'white') + '" fill="' + color + '">' +
                    shape + '</svg>');
                const label = L.DomUtil.create('span', 'pw-legend-label', item);
                label.textContent = _titleCase(stype);
            }

            // Pathways section
            const pathSec = L.DomUtil.create('div', 'pw-legend-section', body);
            const pathTitle = L.DomUtil.create('div', 'pw-legend-section-title', pathSec);
            pathTitle.textContent = 'Pathways';

            const pathTypes = ['conduit', 'aerial', 'direct_buried', 'innerduct',
                'microduct', 'tray', 'raceway', 'submarine'];
            for (let i = 0; i < pathTypes.length; i++) {
                const ptype = pathTypes[i];
                const color = PATHWAY_COLORS[ptype] || '#616161';
                const dash = PATHWAY_DASH[ptype] || '';
                const item = L.DomUtil.create('div', 'pw-legend-item', pathSec);
                const swatch = L.DomUtil.create('span', 'pw-legend-swatch', item);
                _setStaticSvg(swatch,
                    '<svg viewBox="0 0 24 6" width="20" height="6">' +
                    '<line x1="0" y1="3" x2="24" y2="3" stroke="' + color +
                    '" stroke-width="3"' + (dash ? ' stroke-dasharray="' + dash + '"' : '') +
                    '/></svg>');
                const label = L.DomUtil.create('span', 'pw-legend-label', item);
                label.textContent = _titleCase(ptype);
            }

            // Toggle collapse
            header.addEventListener('click', function () {
                const isCollapsed = body.classList.toggle('collapsed');
                header.classList.toggle('collapsed', isCollapsed);
            });

            return container;
        },
    });

    new LegendControl().addTo(map);
}

// ---------------------------------------------------------------------------
// Main initialization
// ---------------------------------------------------------------------------

interface MapInitConfig {
    center?: [number, number];
    zoom?: number;
    bounds?: L.LatLngBoundsExpression;
}

function initializePathwaysMap(elementId: string, config: MapInitConfig): void {
    const container = document.getElementById(elementId);

    // Inject dependencies into sub-modules
    Sidebar.setDeps({
        titleCase: _titleCase,
        esc: _esc,
        debounce: _debounce,
        getCookie: _getCookie,
        structureColors: STRUCTURE_COLORS,
        structureShapes: STRUCTURE_SHAPES,
        pathwayColors: PATHWAY_COLORS,
        apiBase: API_BASE,
    });
    Popover.setDeps({ titleCase: _titleCase });

    const baseLayers = _createBaseLayers();
    const firstLayer = baseLayers[Object.keys(baseLayers)[0]];
    const map = L.map(elementId, {
        layers: [firstLayer],
    });

    // Fit to data extent if bounds provided, otherwise use center/zoom
    if (config.bounds) {
        map.fitBounds(config.bounds, { padding: [30, 30] as [number, number], maxZoom: 17 });
    } else {
        map.setView(config.center || [0, 0], config.zoom || 2);
    }

    // Overlay layers
    const overlayLayers: Record<string, L.Layer> = {};

    // User-configured WMS/WMTS/tile overlays
    const userOverlays = _createUserOverlays();
    for (const name in userOverlays) {
        overlayLayers[name] = userOverlays[name];
    }

    // Layer control
    const layerControl = L.control.layers(baseLayers, overlayLayers, {
        position: 'topright', collapsed: true,
    }).addTo(map);

    // Legend
    _createLegend(map);

    // Counters
    const structureCountEl = document.getElementById('structure-count');
    const pathwayCountEl = document.getElementById('pathway-count');
    const totalLengthEl = document.getElementById('total-length');

    // Zoom hint
    const zoomHint = _createZoomHint(map);

    // --- Layer visibility persistence (localStorage) ---

    const PREFS_KEY = 'pathways_map_layers';
    const DEFAULT_LAYERS: Record<string, boolean> = {
        'Structures': true, 'Conduits': true, 'Aerial Spans': false, 'Direct Buried': false, 'Circuit Routes': false,
    };

    function _loadPrefs(): Record<string, boolean> | null {
        try {
            const saved = localStorage.getItem(PREFS_KEY);
            return saved ? JSON.parse(saved) as Record<string, boolean> : null;
        } catch (_e) { return null; }
    }

    function _savePrefs(layers: Record<string, boolean>): void {
        try { localStorage.setItem(PREFS_KEY, JSON.stringify(layers)); } catch (_e) { /* ignore */ }
    }

    const layerPrefs = _loadPrefs() || DEFAULT_LAYERS;

    // --- Dynamic data layers ---

    const structuresLayer = L.layerGroup();
    const markerClusterGroup = L.markerClusterGroup({
        maxClusterRadius: 35,
        spiderfyOnMaxZoom: true,
        disableClusteringAtZoom: 18,
    });

    const dataLayers: Record<string, L.LayerGroup> = {
        structures: structuresLayer,
        conduits: L.layerGroup(),
        aerialSpans: L.layerGroup(),
        directBuried: L.layerGroup(),
        circuits: L.layerGroup(),
    };

    const layerNames: Record<string, L.LayerGroup> = {
        'Structures': dataLayers.structures,
        'Conduits': dataLayers.conduits,
        'Aerial Spans': dataLayers.aerialSpans,
        'Direct Buried': dataLayers.directBuried,
        'Circuit Routes': dataLayers.circuits,
    };

    // --- External plugin layers ---
    const externalConfigs: ExternalLayerConfig[] = CFG.externalLayers ?? [];
    const externalGroups = initExternalLayers(externalConfigs, map);

    // Add external layers to layerNames for the layer control
    for (const [name, group] of externalGroups) {
        const cfg = getLayerConfig(name);
        if (cfg) {
            layerNames[cfg.label] = group;
        }
    }

    // Add layers based on saved prefs
    for (const lname in layerNames) {
        if (layerPrefs[lname] !== false) {
            layerNames[lname].addTo(map);
        }
    }

    // --- Sidebar layer toggle sync ---

    const _layerCheckboxes: Record<string, HTMLInputElement> = {};

    function _syncSidebarCheckbox(name: string, checked: boolean): void {
        if (_layerCheckboxes[name]) {
            _layerCheckboxes[name].checked = checked;
            const btn = _layerCheckboxes[name].closest('.pw-layer-toggle');
            if (btn) {
                btn.classList.toggle('pw-layer-active', checked);
            }
        }
    }

    // Persist layer toggles
    map.on('overlayadd', function (e: L.LayersControlEvent) {
        const prefs = _loadPrefs() || DEFAULT_LAYERS;
        prefs[e.name] = true;
        _savePrefs(prefs);
        _syncSidebarCheckbox(e.name, true);
    });
    map.on('overlayremove', function (e: L.LayersControlEvent) {
        const prefs = _loadPrefs() || DEFAULT_LAYERS;
        prefs[e.name] = false;
        _savePrefs(prefs);
        _syncSidebarCheckbox(e.name, false);
    });

    // --- Sidebar layer toggles ---

    // SVG icons for layer toggle buttons
    const LAYER_ICONS: Record<string, string> = {
        'Structures': '<svg viewBox="0 0 20 20" width="14" height="14"><circle cx="10" cy="10" r="8" fill="#2e7d32" stroke="white" stroke-width="1.5"/></svg>',
        'Conduits': '<svg viewBox="0 0 20 6" width="18" height="6"><line x1="0" y1="3" x2="20" y2="3" stroke="#795548" stroke-width="3" stroke-dasharray="5 5"/></svg>',
        'Aerial Spans': '<svg viewBox="0 0 20 6" width="18" height="6"><line x1="0" y1="3" x2="20" y2="3" stroke="#1565c0" stroke-width="3" stroke-dasharray="10 5"/></svg>',
        'Direct Buried': '<svg viewBox="0 0 20 6" width="18" height="6"><line x1="0" y1="3" x2="20" y2="3" stroke="#616161" stroke-width="3" stroke-dasharray="2 4"/></svg>',
        'Circuit Routes': '<svg viewBox="0 0 20 6" width="18" height="6"><line x1="0" y1="3" x2="20" y2="3" stroke="#d32f2f" stroke-width="3" stroke-dasharray="8 6"/></svg>',
    };

    function _buildSidebarLayerToggles(): void {
        const toggleContainer = document.getElementById('pw-layer-toggles');
        if (!toggleContainer) return;
        toggleContainer.textContent = '';

        for (const lname in layerNames) {
            const btn = document.createElement('button');
            btn.type = 'button';
            const active = map.hasLayer(layerNames[lname]);
            btn.className = 'pw-layer-toggle' + (active ? ' pw-layer-active' : '');

            // Build button content using DOM methods — icon SVG is from a hardcoded constant
            const iconSvg = LAYER_ICONS[lname] || '';
            const span = document.createElement('span');
            span.textContent = lname;
            const wrapper = document.createElement('span');
            wrapper.innerHTML = iconSvg; // Safe: hardcoded SVG from LAYER_ICONS constant
            while (wrapper.firstChild) btn.appendChild(wrapper.firstChild);
            btn.appendChild(span);

            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.checked = active;
            cb.style.display = 'none';
            _layerCheckboxes[lname] = cb;
            btn.appendChild(cb);

            (function (cbName: string, checkbox: HTMLInputElement, button: HTMLButtonElement) {
                button.addEventListener('click', function () {
                    checkbox.checked = !checkbox.checked;
                    if (checkbox.checked) {
                        map.addLayer(layerNames[cbName]);
                        button.classList.add('pw-layer-active');
                    } else {
                        map.removeLayer(layerNames[cbName]);
                        button.classList.remove('pw-layer-active');
                    }
                    const prefs = _loadPrefs() || DEFAULT_LAYERS;
                    prefs[cbName] = checkbox.checked;
                    _savePrefs(prefs);
                    _loadData();
                });
            })(lname, cb, btn);

            toggleContainer.appendChild(btn);
        }
    }
    _buildSidebarLayerToggles();

    // --- Data loading ---

    function _loadData(): void {
        const zoom = map.getZoom();

        if (zoom < MIN_DATA_ZOOM) {
            structuresLayer.clearLayers();
            dataLayers.conduits.clearLayers();
            dataLayers.aerialSpans.clearLayers();
            dataLayers.directBuried.clearLayers();
            dataLayers.circuits.clearLayers();
            zoomHint.style.display = '';
            if (structureCountEl) structureCountEl.textContent = '-';
            if (pathwayCountEl) pathwayCountEl.textContent = '-';
            if (totalLengthEl) totalLengthEl.textContent = '-';
            Sidebar.setFeatures([]);
            return;
        }

        zoomHint.style.display = 'none';
        const bbox = _bboxParam(map);
        const allFeatures: FeatureEntry[] = [];
        let pendingLoads = 0;
        let totalExpectedLoads = 0;

        if (map.hasLayer(structuresLayer)) totalExpectedLoads++;
        if (map.hasLayer(dataLayers.conduits)) totalExpectedLoads++;
        if (map.hasLayer(dataLayers.aerialSpans)) totalExpectedLoads++;
        if (map.hasLayer(dataLayers.directBuried)) totalExpectedLoads++;
        if (map.hasLayer(dataLayers.circuits)) totalExpectedLoads++;

        let pathwayCount = 0;
        let totalLength = 0;
        let pendingPathway = 0;
        if (map.hasLayer(dataLayers.conduits)) pendingPathway++;
        if (map.hasLayer(dataLayers.aerialSpans)) pendingPathway++;
        if (map.hasLayer(dataLayers.directBuried)) pendingPathway++;
        if (map.hasLayer(dataLayers.circuits)) pendingPathway++;

        function _checkAllLoaded(): void {
            pendingLoads++;
            if (pendingLoads === totalExpectedLoads) {
                Sidebar.setFeatures(allFeatures);
            }
        }

        function _updatePathwayStats(): void {
            if (pathwayCountEl) pathwayCountEl.textContent = String(pathwayCount);
            if (totalLengthEl) totalLengthEl.textContent = (totalLength / 1000).toFixed(2);
        }

        function _pathwayLoaded(data: GeoJSON.FeatureCollection): void {
            const count = data.features ? data.features.length : 0;
            pathwayCount += count;
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
            pendingPathway--;
            if (pendingPathway <= 0) _updatePathwayStats();
        }

        // Structures
        if (map.hasLayer(structuresLayer)) {
            _fetchGeoJSON('structures/', bbox, function (data: GeoJSON.FeatureCollection) {
                structuresLayer.clearLayers();
                markerClusterGroup.clearLayers();

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
                            map.setView(latlng, 15);
                        });
                        structuresLayer.addLayer(marker);
                    });
                    if (structureCountEl) structureCountEl.textContent = String(total);
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
                            Sidebar.onFeatureCreated(entry);
                            layer.on('click', function (e: L.LeafletMouseEvent) {
                                if (e.originalEvent) (e.originalEvent as any)._sidebarClick = true;
                                Sidebar.selectFeature(entry);
                            });
                            layer.on('mouseover', function (e: L.LeafletMouseEvent) {
                                Popover.show(e.latlng || (layer as L.Marker).getLatLng(), feature.properties as GeoJSONProperties);
                            });
                            layer.on('mouseout', function () { Popover.hide(); });
                        },
                    });
                    markerClusterGroup.addLayers(geoLayer.getLayers());
                    structuresLayer.addLayer(markerClusterGroup);
                    if (structureCountEl) {
                        structureCountEl.textContent = String(data.features ? data.features.length : 0);
                    }
                }
                _checkAllLoaded();
            }, { zoom: String(zoom) });
        }

        if (pendingPathway === 0) _updatePathwayStats();

        // Shared pathway handler factory
        function _makePathwayOpts(featureType: FeatureType, styleObj: PathwayStyle): L.GeoJSONOptions {
            return {
                style: function () { return styleObj; },
                onEachFeature: function (feature: GeoJSON.Feature, layer: L.Layer) {
                    if (feature.id != null && (feature.properties as GeoJSONProperties).id == null) {
                        (feature.properties as GeoJSONProperties).id = feature.id as number;
                    }
                    const entry: FeatureEntry = {
                        props: feature.properties as GeoJSONProperties,
                        featureType: featureType,
                        layer: layer,
                        latlng: (layer as L.Polyline).getBounds().getCenter(),
                    };
                    allFeatures.push(entry);
                    Sidebar.onFeatureCreated(entry);
                    layer.on('click', function (e: L.LeafletMouseEvent) {
                        if (e.originalEvent) (e.originalEvent as any)._sidebarClick = true;
                        Sidebar.selectFeature(entry);
                    });
                    layer.on('mouseover', function (e: L.LeafletMouseEvent) {
                        Popover.show(e.latlng, feature.properties as GeoJSONProperties);
                    });
                    layer.on('mouseout', function () { Popover.hide(); });
                },
            };
        }

        // Pathway layer configs
        const pathwayConfigs: [string, L.LayerGroup, FeatureType, PathwayStyle][] = [
            ['conduits/', dataLayers.conduits, 'conduit', { color: '#795548', weight: 3, opacity: 0.7, dashArray: '5 5' }],
            ['aerial-spans/', dataLayers.aerialSpans, 'aerial', { color: '#1565c0', weight: 3, opacity: 0.7, dashArray: '10 5' }],
            ['direct-buried/', dataLayers.directBuried, 'direct_buried', { color: '#616161', weight: 3, opacity: 0.7, dashArray: '2 4' }],
            ['circuits/', dataLayers.circuits, 'circuit', { color: '#d32f2f', weight: 3, opacity: 0.8, dashArray: '8 6' }],
        ];

        pathwayConfigs.forEach(function (cfg) {
            const [endpoint, layer, ftype, style] = cfg;
            if (!map.hasLayer(layer)) return;
            _fetchGeoJSON(endpoint, bbox, function (data: GeoJSON.FeatureCollection) {
                layer.clearLayers();
                const geoLayer = L.geoJSON(data, _makePathwayOpts(ftype, style));
                geoLayer.addTo(layer);
                _addLineLabels(geoLayer, layer, map);
                _pathwayLoaded(data);
                _checkAllLoaded();
            });
        });

        // --- External plugin layers ---
        const visibleExternal = new Set<string>();
        for (const [name, group] of externalGroups) {
            if (map.hasLayer(group)) {
                visibleExternal.add(name);
            }
        }
        if (visibleExternal.size > 0) {
            totalExpectedLoads++;
            loadExternalLayers(bbox, zoom, visibleExternal, function (entry: FeatureEntry, extCfg: ExternalLayerConfig) {
                Sidebar.onFeatureCreated(entry);
                entry.layer.on('click', function (e: L.LeafletMouseEvent) {
                    if (e.originalEvent) (e.originalEvent as any)._sidebarClick = true;
                    Sidebar.selectFeature(entry);
                });
                entry.layer.on('mouseover', function (e: L.LeafletMouseEvent) {
                    Popover.show(e.latlng, entry.props, extCfg.popoverFields);
                });
                entry.layer.on('mouseout', function () { Popover.hide(); });
            }).then(function (extEntries: FeatureEntry[]) {
                for (let i = 0; i < extEntries.length; i++) {
                    allFeatures.push(extEntries[i]);
                }
                _checkAllLoaded();
            });
        }

        // If no layers active, still update sidebar
        if (totalExpectedLoads === 0) {
            Sidebar.setFeatures([]);
        }
    }

    // Load data on move/zoom with debounce
    const debouncedLoad = _debounce(_loadData, 500);
    map.on('moveend', debouncedLoad);

    // Initialize sidebar and popover
    Sidebar.init(map);
    Sidebar.onServerSearch(_serverSearch);
    Popover.init(map);

    // Initial load
    _loadData();

    // Reset view button
    const resetBtn = document.getElementById('reset-view');
    if (resetBtn) {
        resetBtn.addEventListener('click', function () {
            if (config.bounds) {
                map.fitBounds(config.bounds, { padding: [30, 30] as [number, number], maxZoom: 17 });
            } else {
                map.setView(config.center || [0, 0], config.zoom || 2);
            }
        });
    }

    // Store reference
    (window as any).PathwaysMap = {
        map: map,
        layerControl: layerControl,
    };

    // Leaflet calculates size at init; force a recheck after layout settles
    setTimeout(function () { map.invalidateSize(); }, 100);
    window.addEventListener('resize', function () { map.invalidateSize(); });
}

// Expose globally
window.initializePathwaysMap = initializePathwaysMap;

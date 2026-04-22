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
import {
    STRUCTURE_COLORS,
    STRUCTURE_SHAPES,
    PATHWAY_COLORS,
    structureIcon as _structureIcon,
    clusterIcon as _clusterIcon,
    esc as _esc,
    titleCase as _titleCase,
    getCookie as _getCookie,
    bboxParam as _bboxParam,
    debounce as _debounce,
    haversine as _haversine,
} from './map-utils';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const CFG: Partial<PathwaysConfig> = window.PATHWAYS_CONFIG || {};
const API_BASE: string = CFG.apiBase || '/api/plugins/pathways/geo/';
const MAX_NATIVE_ZOOM: number = CFG.maxNativeZoom || 19;
const MIN_DATA_ZOOM = 11;
const MIN_BANK_ZOOM = 18;  // conduit banks only shown past clustering level

// Color & icon maps imported from ./map-utils

// Marker helpers imported from ./map-utils

// Utility helpers imported from ./map-utils

// ---------------------------------------------------------------------------
// GeoJSON fetching with AbortController
// ---------------------------------------------------------------------------

const _inflightControllers: Record<string, AbortController> = {};

interface FetchResult {
    data: GeoJSON.FeatureCollection | null;  // null on 304
    etag: string;
}

async function _fetchGeoJSON(
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
        Sidebar.setServerResults(results);
    } catch {
        _searchController = null;
    }
}

// ---------------------------------------------------------------------------
// Line labels
// ---------------------------------------------------------------------------

function _addLineLabels(geoJsonLayer: L.GeoJSON, layerGroup: L.LayerGroup, map: L.Map): void {
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
        // Angle in screen space (0° = right, positive = clockwise)
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
    'conduit': '5,5', 'conduit_bank': '', 'aerial': '10,5',
    'direct_buried': '2,4', 'innerduct': '8,3', 'microduct': '1,3',
    'tray': '', 'raceway': '12,4', 'submarine': '6,2,2,2',
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

            // Header — collapsed by default
            const header = L.DomUtil.create('div', 'pw-legend-header collapsed', container);
            const chevron = document.createElement('i');
            chevron.className = 'mdi mdi-chevron-down';
            header.appendChild(chevron);
            const titleSpan = document.createElement('span');
            titleSpan.textContent = 'Legend';
            header.appendChild(titleSpan);

            // Body — collapsed by default
            const body = L.DomUtil.create('div', 'pw-legend-body collapsed', container);

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

            const pathTypes = ['conduit', 'conduit_bank', 'aerial', 'direct_buried',
                'innerduct', 'microduct', 'tray', 'raceway', 'submarine'];
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

function _createStatsControl(map: L.Map): void {
    const StatsControl = L.Control.extend({
        options: { position: 'bottomleft' },
        onAdd: function (): HTMLElement {
            const container = L.DomUtil.create('div', 'pw-stats-overlay');
            const sc = L.DomUtil.create('span', '', container);
            sc.id = 'structure-count';
            sc.textContent = '0';
            container.appendChild(document.createTextNode(' structures \u00b7 '));
            const pc = L.DomUtil.create('span', '', container);
            pc.id = 'pathway-count';
            pc.textContent = '0';
            container.appendChild(document.createTextNode(' pathways \u00b7 '));
            const tl = L.DomUtil.create('span', '', container);
            tl.id = 'total-length';
            tl.textContent = '0';
            container.appendChild(document.createTextNode(' km'));
            return container;
        },
    });
    new StatsControl().addTo(map);
}

// ---------------------------------------------------------------------------
// Main initialization
// ---------------------------------------------------------------------------

interface MapInitConfig {
    center?: [number, number];
    zoom?: number;
    bounds?: L.LatLngBoundsExpression;
    kiosk?: boolean;
    select?: string;  // feature ID to auto-select, e.g. "structure-123"
}

function _createSidebarToggleControl(map: L.Map, isKiosk: boolean): L.Control {
    const SidebarToggle = L.Control.extend({
        options: { position: 'topright' as L.ControlPosition },
        onAdd: function (): HTMLElement {
            const container = L.DomUtil.create('div', 'leaflet-control-zoom leaflet-bar pw-sidebar-toggle-ctrl');
            const link = L.DomUtil.create('a', '', container) as HTMLAnchorElement;
            link.href = '#';
            link.title = 'Show sidebar';
            L.DomUtil.create('i', 'mdi mdi-chevron-left', link);
            link.style.display = 'flex';
            link.style.alignItems = 'center';
            link.style.justifyContent = 'center';
            link.style.fontSize = '18px';

            L.DomEvent.disableClickPropagation(container);
            L.DomEvent.on(link, 'click', function (e: Event) {
                L.DomEvent.preventDefault(e);
                Sidebar.show();
            });

            // Watch sidebar visibility to show/hide this button
            const observer = new MutationObserver(function () {
                const sidebar = document.getElementById('pw-sidebar');
                if (!sidebar) return;
                const sidebarVisible = isKiosk
                    ? sidebar.classList.contains('pw-sidebar-open')
                    : !sidebar.classList.contains('pw-sidebar-hidden');
                container.style.display = sidebarVisible ? 'none' : '';
            });
            const sidebar = document.getElementById('pw-sidebar');
            if (sidebar) {
                observer.observe(sidebar, { attributes: true, attributeFilter: ['class'] });
                // Initial state
                const sidebarVisible = isKiosk
                    ? sidebar.classList.contains('pw-sidebar-open')
                    : !sidebar.classList.contains('pw-sidebar-hidden');
                container.style.display = sidebarVisible ? 'none' : '';
            }

            return container;
        },
    });
    return new SidebarToggle();
}

function _createLocateControl(map: L.Map): L.Control {
    const LocateControl = L.Control.extend({
        options: { position: 'topleft' as L.ControlPosition },
        onAdd: function (): HTMLElement {
            const container = L.DomUtil.create('div', 'leaflet-control-zoom leaflet-bar');
            const link = L.DomUtil.create('a', '', container) as HTMLAnchorElement;
            link.href = '#';
            link.title = 'Go to my location';
            L.DomUtil.create('i', 'mdi mdi-crosshairs-gps', link);
            link.style.display = 'flex';
            link.style.alignItems = 'center';
            link.style.justifyContent = 'center';
            link.style.fontSize = '18px';

            L.DomEvent.disableClickPropagation(container);
            L.DomEvent.on(link, 'click', function (e: Event) {
                L.DomEvent.preventDefault(e);
                if (!navigator.geolocation) return;
                navigator.geolocation.getCurrentPosition(
                    function (pos: GeolocationPosition) {
                        map.flyTo([pos.coords.latitude, pos.coords.longitude], 17, { duration: 1 });
                    },
                    function () { /* silently ignore denial */ },
                    { enableHighAccuracy: true, timeout: 10000 },
                );
            });
            return container;
        },
    });
    return new LocateControl();
}

function _createKioskControl(map: L.Map, isKiosk: boolean): L.Control {
    const KioskControl = L.Control.extend({
        options: { position: 'topleft' as L.ControlPosition },
        onAdd: function (): HTMLElement {
            const container = L.DomUtil.create('div', 'leaflet-control-zoom leaflet-bar');
            const link = L.DomUtil.create('a', '', container) as HTMLAnchorElement;
            link.href = '#';
            link.title = isKiosk ? 'Exit kiosk mode' : 'Kiosk mode';
            L.DomUtil.create('i', 'mdi ' + (isKiosk ? 'mdi-fullscreen-exit' : 'mdi-fullscreen'), link);
            link.style.display = 'flex';
            link.style.alignItems = 'center';
            link.style.justifyContent = 'center';
            link.style.fontSize = '18px';

            L.DomEvent.disableClickPropagation(container);
            L.DomEvent.on(link, 'click', function (e: Event) {
                L.DomEvent.preventDefault(e);
                const center = map.getCenter();
                const zoom = map.getZoom();
                const params = new URLSearchParams();
                params.set('lat', center.lat.toFixed(6));
                params.set('lon', center.lng.toFixed(6));
                params.set('zoom', String(zoom));
                if (!isKiosk) {
                    params.set('kiosk', 'true');
                }
                window.location.search = params.toString();
            });
            return container;
        },
    });
    return new KioskControl();
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

    // Fit to bounds if provided, otherwise use center/zoom
    if (config.bounds) {
        // Allow higher zoom when selecting a specific feature vs. viewing full data extent
        const boundsMaxZoom = config.select ? 20 : 17;
        map.fitBounds(config.bounds, { padding: [50, 50] as [number, number], maxZoom: boundsMaxZoom });
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
        position: 'bottomright', collapsed: true,
    }).addTo(map);

    // Stats + legend (stats first so legend stacks above it)
    _createStatsControl(map);
    _createLegend(map);

    // Map controls (topleft, below zoom)
    _createKioskControl(map, !!config.kiosk).addTo(map);
    _createSidebarToggleControl(map, !!config.kiosk).addTo(map);
    _createLocateControl(map).addTo(map);

    // Counters
    const structureCountEl = document.getElementById('structure-count');
    const pathwayCountEl = document.getElementById('pathway-count');
    const totalLengthEl = document.getElementById('total-length');

    // Zoom hint
    const zoomHint = _createZoomHint(map);

    // --- Layer visibility persistence (localStorage) ---

    const PREFS_KEY = 'pathways_map_layers';
    const DEFAULT_LAYERS: Record<string, boolean> = {
        'Structures': true, 'Conduit Banks': true, 'Conduits': true, 'Aerial Spans': false, 'Direct Buried': false, 'Circuit Routes': false,
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
        conduitBanks: L.layerGroup(),
        conduits: L.layerGroup(),
        aerialSpans: L.layerGroup(),
        directBuried: L.layerGroup(),
        circuits: L.layerGroup(),
    };

    const layerNames: Record<string, L.LayerGroup> = {
        'Structures': dataLayers.structures,
        'Conduit Banks': dataLayers.conduitBanks,
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

    // Min zoom per layer display name — layers below this zoom are dimmed
    const LAYER_MIN_ZOOM: Record<string, number> = {
        'Conduit Banks': MIN_BANK_ZOOM,
    };

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
        'Conduit Banks': '<svg viewBox="0 0 20 6" width="18" height="6"><line x1="0" y1="3" x2="20" y2="3" stroke="#ad1457" stroke-width="5"/></svg>',
        'Conduits': '<svg viewBox="0 0 20 6" width="18" height="6"><line x1="0" y1="3" x2="20" y2="3" stroke="#f57c00" stroke-width="3" stroke-dasharray="5 5"/></svg>',
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

    // --- GeoJSON viewport cache ---
    // Overfetch a bbox 50% larger than the viewport and cache the response.
    // When the user pans back to a previously-viewed area at the same zoom,
    // the cached response is reused instantly instead of re-fetching.
    // FIFO eviction keeps memory bounded (≤ GEO_CACHE_SIZE entries per endpoint).

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

    function _cachedFetch(
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

        // Cache miss — expand bbox and fetch
        const dw = (east - west) * OVERFETCH;
        const dh = (north - south) * OVERFETCH;
        const fw = west - dw, fs = south - dh, fe = east + dw, fn = north + dh;
        const fetchBbox = fw + ',' + fs + ',' + fe + ',' + fn;

        _fetchGeoJSON(endpoint, fetchBbox, function (result: FetchResult) {
            if (result.data) {
                _storeInCache(endpoint, fw, fs, fe, fn, zoom, extraKey, result.etag, result.data);
                callback(result.data);
            }
        }, extraParams);
    }

    // After the visible viewport loads, prefetch the 4 cardinal neighbors
    // so panning in any direction hits warm cache.  Runs at idle priority
    // and skips regions already cached.

    let _preloadTimer: ReturnType<typeof setTimeout> | null = null;

    type PreloadSpec = { endpoint: string; extraParams?: Record<string, string | number> };

    const MIN_PRELOAD_ZOOM = 14;  // don't preload at low zoom — user is likely to zoom, not pan

    function _preloadNeighbors(specs: PreloadSpec[]): void {
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
            _fetchGeoJSON(q.endpoint, q.bbox, function (result: FetchResult) {
                if (result.data) {
                    _storeInCache(q.endpoint, q.fw, q.fs, q.fe, q.fn, q.zoom, q.extraKey, result.etag, result.data);
                }
                _preloadTimer = setTimeout(_next, 50);
            }, q.extraParams);
        }

        // Start after a short idle delay so visible data renders first
        _preloadTimer = setTimeout(_next, 200);
    }

    // --- Data loading ---

    function _loadData(): void {
        const zoom = map.getZoom();

        if (zoom < MIN_DATA_ZOOM) {
            structuresLayer.clearLayers();
            dataLayers.conduitBanks.clearLayers();
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

        // Dim toggles for layers unavailable at this zoom
        for (const lname in LAYER_MIN_ZOOM) {
            if (_layerCheckboxes[lname]) {
                const btn = _layerCheckboxes[lname].closest('.pw-layer-toggle');
                if (btn) btn.classList.toggle('pw-layer-unavailable', zoom < LAYER_MIN_ZOOM[lname]);
            }
        }

        const bbox = _bboxParam(map);
        const allFeatures: FeatureEntry[] = [];
        let pendingLoads = 0;
        let totalExpectedLoads = 0;

        // Pathway layer configs: [endpoint, layerGroup, featureType, style, minZoom?]
        const pathwayConfigs: [string, L.LayerGroup, FeatureType, PathwayStyle, number?][] = [
            ['conduit-banks/', dataLayers.conduitBanks, 'conduit_bank', { color: '#ad1457', weight: 5, opacity: 0.8, dashArray: '' }, MIN_BANK_ZOOM],
            ['conduits/', dataLayers.conduits, 'conduit', { color: '#f57c00', weight: 3, opacity: 0.7, dashArray: '5 5' }],
            ['aerial-spans/', dataLayers.aerialSpans, 'aerial', { color: '#1565c0', weight: 3, opacity: 0.7, dashArray: '10 5' }],
            ['direct-buried/', dataLayers.directBuried, 'direct_buried', { color: '#616161', weight: 3, opacity: 0.7, dashArray: '2 4' }],
            ['circuits/', dataLayers.circuits, 'circuit', { color: '#d32f2f', weight: 3, opacity: 0.8, dashArray: '8 6' }],
        ];

        if (map.hasLayer(structuresLayer)) totalExpectedLoads++;
        let pathwayCount = 0;
        let totalLength = 0;
        let pendingPathway = 0;
        pathwayConfigs.forEach(function (cfg) {
            const [, layer, , , minZoom] = cfg;
            if (map.hasLayer(layer) && (!minZoom || zoom >= minZoom)) {
                totalExpectedLoads++;
                pendingPathway++;
            }
        });

        function _checkAllLoaded(): void {
            pendingLoads++;
            if (pendingLoads === totalExpectedLoads) {
                Sidebar.setFeatures(allFeatures);
                // Auto-select feature from URL on first load
                if (_pendingSelectId) {
                    Sidebar.selectById(_pendingSelectId);
                    _pendingSelectId = '';
                }
                // Prefetch cardinal neighbors for all active endpoints
                const specs: PreloadSpec[] = [];
                if (map.hasLayer(structuresLayer)) {
                    specs.push({ endpoint: 'structures/', extraParams: { zoom: zoom } });
                }
                pathwayConfigs.forEach(function (cfg) {
                    const [endpoint, layer, , , minZoom] = cfg;
                    if (map.hasLayer(layer) && (!minZoom || zoom >= minZoom)) {
                        specs.push({ endpoint });
                    }
                });
                _preloadNeighbors(specs);
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
            _cachedFetch('structures/', function (data: GeoJSON.FeatureCollection) {
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
                            // Zoom in progressively — 3 levels deeper per click
                            const nextZoom = Math.min(map.getZoom() + 3, map.getMaxZoom());
                            map.setView(latlng, nextZoom);
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
            }, { zoom: zoom });
        }

        if (pendingPathway === 0) _updatePathwayStats();

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
                    if (!props.name && props.label) props.name = props.label;
                    const entry: FeatureEntry = {
                        props: props,
                        featureType: featureType,
                        layer: layer,
                        latlng: (layer as L.Polyline).getBounds().getCenter(),
                    };
                    allFeatures.push(entry);
                    Sidebar.onFeatureCreated(entry);
                    layer.on('click', function (e: L.LeafletMouseEvent) {
                        if (e.originalEvent) (e.originalEvent as any)._sidebarClick = true;
                        Sidebar.selectFeature(entry);
                        _updateUrl();
                    });
                    layer.on('mouseover', function (e: L.LeafletMouseEvent) {
                        Popover.show(e.latlng, feature.properties as GeoJSONProperties);
                    });
                    layer.on('mouseout', function () { Popover.hide(); });
                },
            };
        }

        pathwayConfigs.forEach(function (cfg) {
            const [endpoint, layer, ftype, style, minZoom] = cfg;
            if (!map.hasLayer(layer)) return;
            if (minZoom && zoom < minZoom) { layer.clearLayers(); return; }
            _cachedFetch(endpoint, function (data: GeoJSON.FeatureCollection) {
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

    // --- URL state management ---

    let _pendingSelectId = config.select || '';

    function _updateUrl(): void {
        const center = map.getCenter();
        const zoom = map.getZoom();
        const params = new URLSearchParams();
        params.set('lat', center.lat.toFixed(6));
        params.set('lon', center.lng.toFixed(6));
        params.set('zoom', String(zoom));
        const selId = Sidebar.getSelectedId();
        if (selId) params.set('select', selId);
        if (config.kiosk) params.set('kiosk', 'true');
        const newUrl = window.location.pathname + '?' + params.toString();
        history.replaceState(null, '', newUrl);
    }

    const debouncedUrlUpdate = _debounce(_updateUrl, 300);

    // Load data on every moveend — AbortController in _fetchGeoJSON cancels
    // stale in-flight requests, so no debounce needed.
    map.on('moveend', function () {
        _loadData();
        debouncedUrlUpdate();
    });

    // Initialize sidebar and popover
    Sidebar.init(map, config.kiosk);
    Sidebar.onServerSearch(_serverSearch);
    Sidebar.onSelectionChange(_updateUrl);
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

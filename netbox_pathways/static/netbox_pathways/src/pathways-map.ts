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
import type { FeatureEntry, FeatureType, GeoJSONProperties, PathwayStyle } from './types/features';
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
    esc as _esc,
    titleCase as _titleCase,
    getCookie as _getCookie,
    bboxParam as _bboxParam,
    debounce as _debounce,
} from './map-utils';
import {
    createMap,
    createZoomHint,
    createLegend,
    createStatsControl,
    createKioskControl,
    createSidebarToggleControl,
    createLocateControl,
} from './map-core';
import type { MapInitConfig } from './map-core';
import {
    API_BASE,
    MIN_DATA_ZOOM,
    MIN_BANK_ZOOM,
    PATHWAY_CONFIGS,
    createDataLayers,
    loadDataLayers,
    calcPathwayLength,
    serverSearch,
} from './data-layers';
import type { DataLayerGroups } from './data-layers';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const CFG: Partial<PathwaysConfig> = window.PATHWAYS_CONFIG || {};

// ---------------------------------------------------------------------------
// Main initialization
// ---------------------------------------------------------------------------

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

    const { map, baseLayers, layerControl } = createMap(elementId, config);

    // Stats + legend (stats first so legend stacks above it)
    createStatsControl(map);
    createLegend(map);

    // Map controls (topleft, below zoom)
    createKioskControl(map, !!config.kiosk).addTo(map);
    createSidebarToggleControl(map, !!config.kiosk, function () { Sidebar.show(); }).addTo(map);
    createLocateControl(map).addTo(map);

    // Counters
    const structureCountEl = document.getElementById('structure-count');
    const pathwayCountEl = document.getElementById('pathway-count');
    const totalLengthEl = document.getElementById('total-length');

    // Zoom hint
    const zoomHint = createZoomHint(map);

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

    const dataLayers = createDataLayers();

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

    // Min zoom per layer display name -- layers below this zoom are dimmed
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

    // SVG icons for layer toggle buttons (trusted compile-time constants)
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

            // Build button content using DOM methods
            // iconSvg is from LAYER_ICONS constant -- trusted compile-time SVG
            const iconSvg = LAYER_ICONS[lname] || '';
            const span = document.createElement('span');
            span.textContent = lname;
            const wrapper = document.createElement('span');
            wrapper.innerHTML = iconSvg; // eslint-disable-line no-unsanitized/property -- trusted compile-time SVG constants only
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

    let pathwayCount = 0;
    let totalLength = 0;

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

    function _loadData(): void {
        const zoom = map.getZoom();

        // Dim toggles for layers unavailable at this zoom
        for (const lname in LAYER_MIN_ZOOM) {
            if (_layerCheckboxes[lname]) {
                const btn = _layerCheckboxes[lname].closest('.pw-layer-toggle');
                if (btn) btn.classList.toggle('pw-layer-unavailable', zoom < LAYER_MIN_ZOOM[lname]);
            }
        }

        // Reset pathway stats
        pathwayCount = 0;
        totalLength = 0;

        loadDataLayers(map, dataLayers, zoomHint, {
            onFeatureClick: function (entry: FeatureEntry, e: L.LeafletMouseEvent) {
                if (e.originalEvent) (e.originalEvent as any)._sidebarClick = true;
                Sidebar.selectFeature(entry);
                _updateUrl();
            },
            onFeatureMouseOver: function (entry: FeatureEntry, e: L.LeafletMouseEvent, feature: GeoJSON.Feature) {
                Popover.show(
                    e.latlng || (entry.layer as L.Marker).getLatLng(),
                    feature.properties as GeoJSONProperties,
                );
            },
            onFeatureMouseOut: function () {
                Popover.hide();
            },
            onFeatureCreated: function (entry: FeatureEntry) {
                Sidebar.onFeatureCreated(entry);
            },
            onStructuresLoaded: function (count: number) {
                if (structureCountEl) structureCountEl.textContent = String(count);
            },
            onPathwayLoaded: function (data: GeoJSON.FeatureCollection) {
                const count = data.features ? data.features.length : 0;
                pathwayCount += count;
                totalLength += calcPathwayLength(data);
                if (pathwayCountEl) pathwayCountEl.textContent = String(pathwayCount);
                if (totalLengthEl) totalLengthEl.textContent = (totalLength / 1000).toFixed(2);
            },
            onAllLoaded: function (allFeatures: FeatureEntry[]) {
                if (zoom < MIN_DATA_ZOOM) {
                    if (structureCountEl) structureCountEl.textContent = '-';
                    if (pathwayCountEl) pathwayCountEl.textContent = '-';
                    if (totalLengthEl) totalLengthEl.textContent = '-';
                    Sidebar.setFeatures([]);
                    return;
                }

                // --- External plugin layers ---
                const visibleExternal = new Set<string>();
                for (const [name, group] of externalGroups) {
                    if (map.hasLayer(group)) {
                        visibleExternal.add(name);
                    }
                }
                if (visibleExternal.size > 0) {
                    const bbox = _bboxParam(map);
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
                        Sidebar.setFeatures(allFeatures);
                        // Auto-select feature from URL on first load
                        if (_pendingSelectId) {
                            Sidebar.selectById(_pendingSelectId);
                            _pendingSelectId = '';
                        }
                    });
                } else {
                    Sidebar.setFeatures(allFeatures);
                    // Auto-select feature from URL on first load
                    if (_pendingSelectId) {
                        Sidebar.selectById(_pendingSelectId);
                        _pendingSelectId = '';
                    }
                }
            },
        });
    }

    // --- URL state management ---

    let _pendingSelectId = config.select || '';

    const debouncedUrlUpdate = _debounce(_updateUrl, 300);

    // Load data on every moveend -- AbortController in fetchGeoJSON cancels
    // stale in-flight requests, so no debounce needed.
    map.on('moveend', function () {
        _loadData();
        debouncedUrlUpdate();
    });

    // Initialize sidebar and popover
    Sidebar.init(map, config.kiosk);
    Sidebar.onServerSearch(function (query: string) {
        serverSearch(query, function (results) {
            Sidebar.setServerResults(results);
        });
    });
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

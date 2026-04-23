/**
 * Route planner map entry point.
 *
 * Tiles + legend only. No infrastructure data layers.
 * Route overlay (pathways + structures) rendered after HTMX results,
 * using the same styling as the main infrastructure map.
 * Map bounds are locked to the route extent once found.
 */

import {
    createMap,
    createLegend,
} from './map-core';
import type { MapInitConfig } from './map-core';
import {
    STRUCTURE_COLORS,
    STRUCTURE_SHAPES,
    structureIcon as _structureIcon,
    pathwayStyle as _pathwayStyle,
    titleCase as _titleCase,
} from './map-utils';
import { Popover } from './popover';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RoutePlannerPathway {
    pk: number;
    label?: string;
    type?: string;        // display name
    pathway_type?: string; // raw key for style lookup
    coords: [number, number][];
}

interface RoutePlannerStructure {
    pk: number;
    label: string;
    structure_type?: string;
    geo: [number, number];  // [lat, lon]
    role: 'start' | 'mid' | 'end';
    type?: string;
}

interface RouteGeometryData {
    pathways: RoutePlannerPathway[];
    structures: RoutePlannerStructure[];
}

// ---------------------------------------------------------------------------
// Highlight state — per-instance to support multiple maps on one page
// ---------------------------------------------------------------------------

interface HighlightState {
    layer: L.Layer | null;
    outline: L.Polyline | null;
}

function _createHighlightState(): HighlightState {
    return { layer: null, outline: null };
}

function _lighten(hex: string, amount: number): string {
    const num = parseInt(hex.replace('#', ''), 16);
    const r = Math.min(255, ((num >> 16) & 0xff) + Math.round(255 * amount));
    const g = Math.min(255, ((num >> 8) & 0xff) + Math.round(255 * amount));
    const b = Math.min(255, (num & 0xff) + Math.round(255 * amount));
    return '#' + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
}

function _unhighlight(map: L.Map, hl: HighlightState): void {
    if (hl.outline) {
        hl.outline.remove();
        hl.outline = null;
    }
    if (hl.layer) {
        const layer = hl.layer as Record<string, any>;
        if (layer._origIcon) {
            (layer as any).setIcon(layer._origIcon);
            delete layer._origIcon;
        }
        if (layer._origStyle && typeof (layer as any).setStyle === 'function') {
            (layer as any).setStyle(layer._origStyle);
            delete layer._origStyle;
        }
        hl.layer = null;
    }
}

function _highlightStructure(map: L.Map, hl: HighlightState, marker: L.Marker, structureType: string): void {
    _unhighlight(map, hl);
    hl.layer = marker;
    const m = marker as L.Marker & { _origIcon?: L.Icon | L.DivIcon };
    m._origIcon = (m as any).getIcon();
    const color = STRUCTURE_COLORS[structureType] || '#616161';
    const shape = STRUCTURE_SHAPES[structureType] || '<circle cx="10" cy="10" r="8"/>';
    const isOutline = shape.includes('fill="none"');
    m.setIcon(L.divIcon({
        className: 'pw-marker pw-marker-selected',
        html: '<svg class="pw-marker-svg" viewBox="0 0 20 20" width="26" height="26"' +
              ' stroke="' + (isOutline ? color : 'white') +
              '" fill="' + color + '">' + shape + '</svg>',
        iconSize: [26, 26] as [number, number],
        iconAnchor: [13, 13] as [number, number],
        popupAnchor: [0, -14] as [number, number],
    }));
}

function _highlightPathway(map: L.Map, hl: HighlightState, polyline: L.Polyline): void {
    _unhighlight(map, hl);
    hl.layer = polyline;
    const pl = polyline as L.Polyline & { _origStyle?: L.PathOptions };
    const opts = (pl as any).options || {};
    pl._origStyle = {
        weight: opts.weight || 3,
        opacity: opts.opacity || 0.7,
        color: opts.color,
        dashArray: opts.dashArray,
    };
    const latlngs = pl.getLatLngs() as L.LatLng[];
    if (latlngs && latlngs.length > 0) {
        hl.outline = L.polyline(latlngs, {
            color: _lighten(opts.color || '#888', 0.55),
            weight: 12,
            opacity: 0.5,
            interactive: false,
        }).addTo(map);
    }
    pl.setStyle({ weight: 6, opacity: 1, dashArray: '' });
}

// ---------------------------------------------------------------------------
// Route overlay rendering
// ---------------------------------------------------------------------------

interface RenderedFeature {
    layer: L.Layer;
    kind: 'structure' | 'pathway';
    structureType?: string;
    latlng: L.LatLng;
}

// Per-instance select callback, set by _renderRouteOverlay's caller
type OnSelectFn = (kind: string, pk: number) => void;

interface LayerState {
    routeLayer: L.FeatureGroup | null;
    markerLayer: L.FeatureGroup | null;
    syncToWindow: boolean;  // only the route planner page syncs to window globals
}

function _renderRouteOverlay(map: L.Map, data: RouteGeometryData, state: LayerState, onSelect?: OnSelectFn): RenderedFeature[] {
    // Clear previous route layers for THIS map instance
    if (state.routeLayer) { map.removeLayer(state.routeLayer); state.routeLayer = null; }
    if (state.markerLayer) { map.removeLayer(state.markerLayer); state.markerLayer = null; }

    const features: RenderedFeature[] = [];
    if (!data.pathways || data.pathways.length === 0) return features;

    const routeGroup = L.featureGroup();
    const markerGroup = L.featureGroup();

    // Draw each pathway segment with proper style
    data.pathways.forEach(function (pw) {
        if (!pw.coords || pw.coords.length < 2) return;
        const latlngs = pw.coords.map(function (c) { return [c[1], c[0]] as [number, number]; });
        const style = _pathwayStyle(pw.pathway_type || '');
        const props = { id: pw.pk, name: pw.label || '', pathway_type: pw.pathway_type || '' };
        const polyline = L.polyline(latlngs, style).addTo(routeGroup);
        polyline.on('mouseover', function (e: L.LeafletMouseEvent) { Popover.show(e.latlng, props as any); });
        polyline.on('mousemove', function (e: L.LeafletMouseEvent) { Popover.show(e.latlng, props as any); });
        polyline.on('mouseout', function () { Popover.hide(); });
        polyline.on('click', function (e: L.LeafletMouseEvent) {
            if (e.originalEvent) (e.originalEvent as any)._featureClick = true;
            if (onSelect) onSelect('pathway', pw.pk);
        });
        (polyline as any)._rpPk = pw.pk;
        const mid = latlngs[Math.floor(latlngs.length / 2)];
        features.push({
            layer: polyline,
            kind: 'pathway',
            latlng: L.latLng(mid[0], mid[1]),
        });
    });

    // Structure markers — proper icons matching main map
    if (data.structures) {
        data.structures.forEach(function (s) {
            if (!s.geo) return;
            const stype = s.structure_type || '';
            const isEndpoint = (s.role === 'start' || s.role === 'end');
            const sz = isEndpoint ? 24 : 20;
            const icon = _structureIcon(stype, sz);

            // For start/end, wrap with a colored ring
            if (isEndpoint) {
                const fill = STRUCTURE_COLORS[stype] || '#616161';
                const shape = STRUCTURE_SHAPES[stype] || '<circle cx="10" cy="10" r="8"/>';
                const isOutline = shape.includes('fill="none"');
                const ringColor = s.role === 'start' ? '#2fb344' : '#d63939';
                const half = sz / 2;
                const ringIcon = L.divIcon({
                    className: 'pw-marker',
                    html: '<svg xmlns="http://www.w3.org/2000/svg" width="' + sz + '" height="' + sz + '">'
                        + '<circle cx="' + half + '" cy="' + half + '" r="' + (half - 1) + '" fill="none" stroke="' + ringColor + '" stroke-width="3"/>'
                        + '<g transform="translate(2,2) scale(' + ((sz - 4) / 20) + ')"'
                        + ' fill="' + fill + '" stroke="' + (isOutline ? fill : 'white') + '">'
                        + shape + '</g></svg>',
                    iconSize: [sz, sz] as [number, number],
                    iconAnchor: [half, half] as [number, number],
                    popupAnchor: [0, -(half + 2)] as [number, number],
                });
                const marker = L.marker([s.geo[0], s.geo[1]], { icon: ringIcon }).addTo(markerGroup);
                const sProps = { id: s.pk, name: s.label, structure_type: stype };
                marker.on('mouseover', function (e: L.LeafletMouseEvent) { Popover.show(e.latlng || marker.getLatLng(), sProps as any); });
                marker.on('mouseout', function () { Popover.hide(); });
                marker.on('click', function (e: L.LeafletMouseEvent) {
                    if (e.originalEvent) (e.originalEvent as any)._featureClick = true;
                    if (onSelect) onSelect('structure', s.pk);
                });
                (marker as any)._rpPk = s.pk;
                features.push({
                    layer: marker,
                    kind: 'structure',
                    structureType: stype,
                    latlng: L.latLng(s.geo[0], s.geo[1]),
                });
            } else {
                const marker = L.marker([s.geo[0], s.geo[1]], { icon }).addTo(markerGroup);
                const sProps = { id: s.pk, name: s.label, structure_type: stype };
                marker.on('mouseover', function (e: L.LeafletMouseEvent) { Popover.show(e.latlng || marker.getLatLng(), sProps as any); });
                marker.on('mouseout', function () { Popover.hide(); });
                marker.on('click', function (e: L.LeafletMouseEvent) {
                    if (e.originalEvent) (e.originalEvent as any)._featureClick = true;
                    if (onSelect) onSelect('structure', s.pk);
                });
                (marker as any)._rpPk = s.pk;
                features.push({
                    layer: marker,
                    kind: 'structure',
                    structureType: stype,
                    latlng: L.latLng(s.geo[0], s.geo[1]),
                });
            }
        });
    }

    routeGroup.addTo(map);
    markerGroup.addTo(map);
    state.routeLayer = routeGroup;
    state.markerLayer = markerGroup;
    if (state.syncToWindow) {
        window._rpRouteLayer = routeGroup;
        window._rpMarkerLayer = markerGroup;
    }

    // Fit and lock bounds to the route
    const allBounds = routeGroup.getBounds();
    if (allBounds.isValid()) {
        const padded = allBounds.pad(0.15);
        map.fitBounds(padded);
        map.setMaxBounds(padded.pad(0.5));
        map.setMinZoom(map.getBoundsZoom(padded.pad(0.5)));
    }

    return features;
}

// ---------------------------------------------------------------------------
// Main entry point
// ---------------------------------------------------------------------------

function initializeRoutePlannerMap(elementId: string, config: MapInitConfig): void {
    const { map } = createMap(elementId, config);

    // Static route display (PlannedRoute detail) — per-instance, no singletons
    if (config.routeData) {
        // Create a per-instance popover element (not the Popover singleton)
        const popEl = document.createElement('div');
        popEl.className = 'pw-popover';
        popEl.style.display = 'none';
        map.getContainer().appendChild(popEl);

        function _showPop(latlng: L.LatLng, name: string, typeName: string): void {
            popEl.textContent = '';
            const nameSpan = document.createElement('span');
            nameSpan.className = 'pw-popover-name';
            nameSpan.textContent = name;
            popEl.appendChild(nameSpan);
            if (typeName) {
                const typeSpan = document.createElement('span');
                typeSpan.className = 'pw-popover-type';
                typeSpan.textContent = typeName;
                popEl.appendChild(typeSpan);
            }
            const pt = map.latLngToContainerPoint(latlng);
            const cw = map.getContainer().clientWidth;
            let x = pt.x + 14;
            if (x + 200 > cw) x = pt.x - 200;
            popEl.style.left = x + 'px';
            popEl.style.top = (pt.y - 10) + 'px';
            popEl.style.display = '';
        }
        function _hidePop(): void { popEl.style.display = 'none'; }

        const staticState: LayerState = { routeLayer: null, markerLayer: null, syncToWindow: false };
        const hl = _createHighlightState();
        const rd = config.routeData as RouteGeometryData;
        if (rd.structures) {
            rd.structures.forEach(function (s: any) {
                if (!s.role) {
                    if (s.is_start) s.role = 'start';
                    else if (s.is_end) s.role = 'end';
                    else s.role = 'mid';
                }
            });
        }

        // Build feature map and instance-scoped select callback
        const featureMap: Record<string, RenderedFeature> = {};
        const localSelect: OnSelectFn = function (kind, pk) {
            const feat = featureMap[kind + '-' + pk];
            if (!feat) return;
            const zoom = map.getZoom();
            const minZoom = kind === 'structure' ? 18 : 16;
            if (zoom < minZoom) {
                map.flyTo(feat.latlng, minZoom, { duration: 0.5 });
            } else {
                map.panTo(feat.latlng);
            }
            if (feat.kind === 'structure') {
                _highlightStructure(map, hl, feat.layer as L.Marker, feat.structureType || '');
            } else {
                _highlightPathway(map, hl, feat.layer as L.Polyline);
            }
        };

        // Render overlay — click handlers use localSelect via closure
        const features = _renderRouteOverlay(map, rd, staticState, localSelect);
        features.forEach(function (f) {
            const pk = (f.layer as any)._rpPk;
            if (pk != null) featureMap[f.kind + '-' + pk] = f;
        });

        // Re-wire hover events to use local popover instead of Popover singleton
        features.forEach(function (f) {
            const layer = f.layer as any;
            const pk = layer._rpPk;
            let name = '';
            let typeName = '';
            if (f.kind === 'structure' && rd.structures) {
                const s = rd.structures.find(function (s) { return s.pk === pk; });
                if (s) { name = s.label; typeName = s.structure_type ? _titleCase(s.structure_type) : ''; }
            } else if (f.kind === 'pathway' && rd.pathways) {
                const p = rd.pathways.find(function (p) { return p.pk === pk; });
                if (p) { name = p.label || ''; typeName = p.pathway_type ? _titleCase(p.pathway_type) : ''; }
            }
            layer.off('mouseover').off('mousemove').off('mouseout');
            layer.on('mouseover', function (e: L.LeafletMouseEvent) { _showPop(e.latlng || layer.getLatLng(), name, typeName); });
            layer.on('mousemove', function (e: L.LeafletMouseEvent) { _showPop(e.latlng || layer.getLatLng(), name, typeName); });
            layer.on('mouseout', function () { _hidePop(); });
        });

        // Click on empty map clears highlight
        map.on('click', function (e: L.LeafletMouseEvent) {
            if ((e.originalEvent as any)?._featureClick) return;
            _unhighlight(map, hl);
        });

        setTimeout(function () { map.invalidateSize(); }, 100);
        return;
    }

    // --- Route planner mode (full interactive) ---
    createLegend(map);
    Popover.setDeps({ titleCase: _titleCase });
    Popover.init(map);

    const layerState: LayerState = { routeLayer: null, markerLayer: null, syncToWindow: true };
    const rpHl = _createHighlightState();

    window._rpMap = map;
    window._rpRouteLayer = null;
    window._rpMarkerLayer = null;

    // Session storage key — scoped to the current URL so different cables don't collide
    const CACHE_KEY = 'pw_route_result_' + window.location.pathname + window.location.search;

    // Shared select handler: center map, highlight feature, sync hop list.
    function _selectFeature(kind: string, pk: number, featureMap: Record<string, RenderedFeature>): void {
        const feat = featureMap[kind + '-' + pk];
        if (!feat) return;

        const zoom = map.getZoom();
        const minZoom = kind === 'structure' ? 18 : 16;
        if (zoom < minZoom) {
            map.flyTo(feat.latlng, minZoom, { duration: 0.5 });
        } else {
            map.panTo(feat.latlng);
        }

        if (feat.kind === 'structure') {
            _highlightStructure(map, rpHl, feat.layer as L.Marker, feat.structureType || '');
        } else {
            _highlightPathway(map, rpHl, feat.layer as L.Polyline);
        }

        // Sync hop list active state
        const hopItems = document.querySelectorAll('[data-hop-kind][data-hop-pk]');
        hopItems.forEach(function (h) {
            const hKind = (h as HTMLElement).dataset.hopKind;
            const hPk = (h as HTMLElement).dataset.hopPk;
            h.classList.toggle('pw-hop-active', hKind === kind && hPk === String(pk));
        });
    }

    // Build per-render onSelect callback, wire hop list clicks
    let _rpOnSelect: OnSelectFn | null = null;

    function _wireInteractions(features: RenderedFeature[]): void {
        const featureMap: Record<string, RenderedFeature> = {};
        features.forEach(function (f) {
            const pk = (f.layer as any)._rpPk;
            if (pk != null) featureMap[f.kind + '-' + pk] = f;
        });

        _rpOnSelect = function (kind: string, pk: number) {
            _selectFeature(kind, pk, featureMap);
        };

        // Hop list clicks
        const hopItems = document.querySelectorAll('[data-hop-kind][data-hop-pk]');
        hopItems.forEach(function (item) {
            item.addEventListener('click', function (e) {
                if ((e.target as HTMLElement).closest('a')) return;
                const kind = (item as HTMLElement).dataset.hopKind || '';
                const pk = parseInt((item as HTMLElement).dataset.hopPk || '0', 10);
                _selectFeature(kind, pk, featureMap);
            });
        });
    }

    // Render route + wire interactions. Used by both HTMX handler and cache restore.
    function _applyRoute(data: RouteGeometryData): void {
        map.setMaxBounds(null as unknown as L.LatLngBoundsExpression);
        map.setMinZoom(1);
        _unhighlight(map, rpHl);
        const rpSelect: OnSelectFn = function (kind, pk) { if (_rpOnSelect) _rpOnSelect(kind, pk); };
        const features = _renderRouteOverlay(map, data, layerState, rpSelect);
        _wireInteractions(features);
    }

    // Listen for HTMX results — save to sessionStorage + render
    document.body.addEventListener('htmx:afterSettle', function (evt: Event) {
        const detail = (evt as CustomEvent).detail;
        if (!detail || !detail.target || detail.target.id !== 'planner-results') return;

        const dataEl = document.getElementById('route-geometry-data');
        if (!dataEl) {
            if (layerState.routeLayer) { map.removeLayer(layerState.routeLayer); layerState.routeLayer = null; }
            if (layerState.markerLayer) { map.removeLayer(layerState.markerLayer); layerState.markerLayer = null; }
            if (layerState.syncToWindow) { window._rpRouteLayer = null; window._rpMarkerLayer = null; }
            try { sessionStorage.removeItem(CACHE_KEY); } catch (_e) { /* ignore */ }
            return;
        }

        let data: RouteGeometryData;
        try {
            data = JSON.parse(dataEl.textContent || '{}') as RouteGeometryData;
        } catch (e) { return; }

        // Save geometry + results HTML for back-navigation restore.
        // The HTML originates from our own Django template (server-rendered,
        // not user input), so restoring it from sessionStorage is safe.
        try {
            const resultsEl = document.getElementById('planner-results');
            sessionStorage.setItem(CACHE_KEY, JSON.stringify({
                geometry: data,
                resultsHtml: resultsEl ? resultsEl.innerHTML : '',  // eslint-disable-line no-unsanitized/property
            }));
        } catch (_e) { /* ignore quota errors */ }

        _applyRoute(data);
    });

    // Restore route from sessionStorage on page load (back-navigation).
    // The cached HTML was originally rendered by our Django template, not user input.
    try {
        const cached = sessionStorage.getItem(CACHE_KEY);
        if (cached) {
            const parsed = JSON.parse(cached) as { geometry: RouteGeometryData; resultsHtml: string };
            if (parsed.geometry && parsed.geometry.pathways && parsed.geometry.pathways.length > 0) {
                const resultsEl = document.getElementById('planner-results');
                if (resultsEl && parsed.resultsHtml) {
                    resultsEl.innerHTML = parsed.resultsHtml;  // eslint-disable-line no-unsanitized/property
                }
                setTimeout(function () {
                    _applyRoute(parsed.geometry);
                }, 100);
            }
        }
    } catch (_e) { /* ignore parse errors */ }

    // Click on empty map clears highlight + hop list active state
    map.on('click', function (e: L.LeafletMouseEvent) {
        // Don't clear if a feature click handler already ran
        if ((e.originalEvent as any)?._featureClick) return;
        _unhighlight(map, rpHl);
        document.querySelectorAll('.pw-hop-active').forEach(function (el) {
            el.classList.remove('pw-hop-active');
        });
    });

    // Leaflet size recalc
    setTimeout(function () { map.invalidateSize(); }, 100);
    window.addEventListener('resize', function () { map.invalidateSize(); });
}

// Expose globally
window.initializeRoutePlannerMap = initializeRoutePlannerMap;
window.pwStructureIcon = _structureIcon;
window.pwPathwayStyle = _pathwayStyle;
window.pwPopover = Popover;
window.pwTitleCase = _titleCase;

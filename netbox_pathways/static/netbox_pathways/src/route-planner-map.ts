/**
 * Route planner map entry point.
 *
 * Tiles + legend only. No infrastructure data layers.
 * Route overlay (pathways + structures) rendered after HTMX results.
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
} from './map-utils';

// ---------------------------------------------------------------------------
// Route overlay rendering
// ---------------------------------------------------------------------------

interface RoutePlannerPathway {
    pk: number;
    label?: string;
    type?: string;
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

function _renderRouteOverlay(map: L.Map, data: RouteGeometryData): void {
    // Clear previous route layers
    if (window._rpRouteLayer) { map.removeLayer(window._rpRouteLayer); window._rpRouteLayer = null; }
    if (window._rpMarkerLayer) { map.removeLayer(window._rpMarkerLayer); window._rpMarkerLayer = null; }

    if (!data.pathways || data.pathways.length === 0) return;

    const routeGroup = L.featureGroup();
    const markerGroup = L.featureGroup();

    // Draw each pathway segment
    data.pathways.forEach(function (pw) {
        if (pw.coords && pw.coords.length > 1) {
            const latlngs = pw.coords.map(function (c) { return [c[1], c[0]] as [number, number]; });
            L.polyline(latlngs, {
                color: '#206bc4',
                weight: 4,
                opacity: 0.85,
            }).bindPopup('<strong>' + (pw.label || 'Pathway') + '</strong><br>' + (pw.type || ''))
              .addTo(routeGroup);
        }
    });

    // Structure markers — SVG icons matching main map style
    if (data.structures) {
        data.structures.forEach(function (s) {
            if (!s.geo) return;
            const stype = s.structure_type || '';
            const fill = STRUCTURE_COLORS[stype] || '#666';
            const shape = STRUCTURE_SHAPES[stype] || '<circle cx="10" cy="10" r="8"/>';
            const isEndpoint = (s.role === 'start' || s.role === 'end');
            const sz = isEndpoint ? 24 : 20;
            const ringColor = s.role === 'start' ? '#2fb344' : (s.role === 'end' ? '#d63939' : 'none');
            const ring = isEndpoint
                ? '<circle cx="' + (sz / 2) + '" cy="' + (sz / 2) + '" r="' + (sz / 2 - 1) + '" fill="none" stroke="' + ringColor + '" stroke-width="3"/>'
                : '';
            const innerOffset = isEndpoint ? 2 : 0;
            const innerScale = isEndpoint ? (sz - 4) / 20 : 1;
            const svgHtml = '<svg xmlns="http://www.w3.org/2000/svg" width="' + sz + '" height="' + sz + '">'
                + ring
                + '<g transform="translate(' + innerOffset + ',' + innerOffset + ') scale(' + innerScale + ')" '
                + 'fill="' + fill + '" stroke="' + fill + '">'
                + shape + '</g></svg>';
            const icon = L.divIcon({
                html: svgHtml,
                className: '',
                iconSize: [sz, sz] as [number, number],
                iconAnchor: [sz / 2, sz / 2] as [number, number],
                popupAnchor: [0, -sz / 2] as [number, number],
            });
            L.marker([s.geo[0], s.geo[1]], { icon: icon })
              .bindPopup(
                  '<strong>' + s.label + '</strong>' +
                  (s.type ? '<br><small>' + s.type + '</small>' : ''),
              ).addTo(markerGroup);
        });
    }

    routeGroup.addTo(map);
    markerGroup.addTo(map);
    window._rpRouteLayer = routeGroup;
    window._rpMarkerLayer = markerGroup;

    // Fit and lock bounds to the route
    const allBounds = routeGroup.getBounds();
    if (allBounds.isValid()) {
        const padded = allBounds.pad(0.15);
        map.fitBounds(padded);
        map.setMaxBounds(padded.pad(0.5));  // allow slight panning beyond route
        map.setMinZoom(map.getBoundsZoom(padded.pad(0.5)));
    }
}

// ---------------------------------------------------------------------------
// Main entry point
// ---------------------------------------------------------------------------

function initializeRoutePlannerMap(elementId: string, config: MapInitConfig): void {
    const { map } = createMap(elementId, config);

    // Legend only — no data layers, no infrastructure features
    createLegend(map);

    // Expose map reference for the inline form JS
    window._rpMap = map;
    window._rpRouteLayer = null;
    window._rpMarkerLayer = null;

    // Listen for HTMX results
    document.body.addEventListener('htmx:afterSettle', function (evt: Event) {
        const detail = (evt as CustomEvent).detail;
        if (!detail || !detail.target || detail.target.id !== 'planner-results') return;

        // Clear previous
        if (window._rpRouteLayer) { map.removeLayer(window._rpRouteLayer); window._rpRouteLayer = null; }
        if (window._rpMarkerLayer) { map.removeLayer(window._rpMarkerLayer); window._rpMarkerLayer = null; }
        // Reset bounds lock from previous route
        map.setMaxBounds(null as unknown as L.LatLngBoundsExpression);
        map.setMinZoom(1);

        const dataEl = document.getElementById('route-geometry-data');
        if (!dataEl) return;

        let data: RouteGeometryData;
        try {
            data = JSON.parse(dataEl.textContent || '{}') as RouteGeometryData;
        } catch (e) { return; }

        _renderRouteOverlay(map, data);

        // Wire up click-to-center on hop list items
        const hopItems = document.querySelectorAll('[data-hop-lat][data-hop-lon]');
        hopItems.forEach(function (item) {
            (item as HTMLElement).style.cursor = 'pointer';
            item.addEventListener('click', function (e) {
                if ((e.target as HTMLElement).closest('a')) return;
                const lat = parseFloat((item as HTMLElement).dataset.hopLat || '0');
                const lon = parseFloat((item as HTMLElement).dataset.hopLon || '0');
                if (lat && lon) {
                    map.flyTo([lat, lon], 18, { duration: 0.5 });
                }
            });
        });
    });

    // Leaflet size recalc after layout settles
    setTimeout(function () { map.invalidateSize(); }, 100);
    window.addEventListener('resize', function () { map.invalidateSize(); });
}

// Expose globally
window.initializeRoutePlannerMap = initializeRoutePlannerMap;

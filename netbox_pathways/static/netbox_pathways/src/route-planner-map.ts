/**
 * Route planner map entry point.
 *
 * Reuses map-core for base layers/controls and data-layers for
 * infrastructure rendering.  Adds route overlay rendering driven
 * by HTMX results.
 */

import {
    createMap,
    createLegend,
} from './map-core';
import type { MapInitConfig } from './map-core';
import {
    createDataLayers,
    loadDataLayers,
    MIN_DATA_ZOOM,
} from './data-layers';
import {
    STRUCTURE_COLORS,
    STRUCTURE_SHAPES,
    structureIcon as _structureIcon,
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

    // Structure markers -- match main map style (SVG shapes + type colors)
    if (data.structures) {
        data.structures.forEach(function (s) {
            if (!s.geo) return;
            const stype = s.structure_type || '';
            const fill = STRUCTURE_COLORS[stype] || '#666';
            const shape = STRUCTURE_SHAPES[stype] || '<circle cx="10" cy="10" r="7"/>';
            const isEndpoint = (s.role === 'start' || s.role === 'end');
            const sz = isEndpoint ? 24 : 20;
            const ringColor = s.role === 'start' ? '#2fb344' : (s.role === 'end' ? '#d63939' : 'none');
            const ring = isEndpoint
                ? '<circle cx="' + (sz / 2) + '" cy="' + (sz / 2) + '" r="' + (sz / 2 - 1) + '" fill="none" stroke="' + ringColor + '" stroke-width="3"/>'
                : '';
            // Scale the inner shape to fit
            const innerOffset = isEndpoint ? 2 : 0;
            const innerScale = isEndpoint ? (sz - 4) / 20 : 1;
            const svgHtml = '<svg xmlns="http://www.w3.org/2000/svg" width="' + sz + '" height="' + sz + '">'
                + ring
                + '<g transform="translate(' + innerOffset + ',' + innerOffset + ') scale(' + innerScale + ')" '
                + 'fill="' + fill + '" stroke="' + fill + '">'
                + shape + '</g></svg>';
            const icon = L.divIcon({
                html: svgHtml, // Trusted: built from compile-time STRUCTURE_COLORS/STRUCTURE_SHAPES constants
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

    // Fit map to route bounds
    const allBounds = routeGroup.getBounds();
    if (allBounds.isValid()) {
        map.fitBounds(allBounds.pad(0.15));
    }
}

// ---------------------------------------------------------------------------
// Main entry point
// ---------------------------------------------------------------------------

function initializeRoutePlannerMap(elementId: string, config: MapInitConfig): void {
    const { map, baseLayers, layerControl } = createMap(elementId, config);

    // Legend
    createLegend(map);

    // Infrastructure data layers (same rendering as main map, no sidebar/popover)
    const dataLayers = createDataLayers();

    // Add all infrastructure layers to the map and layer control
    const layerNames: Record<string, L.LayerGroup> = {
        'Structures': dataLayers.structures,
        'Conduit Banks': dataLayers.conduitBanks,
        'Conduits': dataLayers.conduits,
        'Aerial Spans': dataLayers.aerialSpans,
        'Direct Buried': dataLayers.directBuried,
        'Circuit Routes': dataLayers.circuits,
    };

    for (const lname in layerNames) {
        layerNames[lname].addTo(map);
        layerControl.addOverlay(layerNames[lname], lname);
    }

    // Load data on map move
    function _loadData(): void {
        loadDataLayers(map, dataLayers, null, {});
    }

    map.on('moveend', _loadData);
    _loadData();

    // Expose map reference for the inline form JS
    window._rpMap = map;
    window._rpRouteLayer = null;
    window._rpMarkerLayer = null;

    // Listen for HTMX results
    const resultsEl = document.getElementById('planner-results');
    if (resultsEl) {
        resultsEl.addEventListener('htmx:afterSettle', function () {
            // Clear previous
            if (window._rpRouteLayer) { map.removeLayer(window._rpRouteLayer); window._rpRouteLayer = null; }
            if (window._rpMarkerLayer) { map.removeLayer(window._rpMarkerLayer); window._rpMarkerLayer = null; }

            const dataEl = document.getElementById('route-geometry-data');
            if (!dataEl) return;

            let data: RouteGeometryData;
            try {
                data = JSON.parse(dataEl.textContent || '{}') as RouteGeometryData;
            } catch (e) { return; }

            _renderRouteOverlay(map, data);
        });
    }

    // Leaflet calculates size at init; force a recheck after layout settles
    setTimeout(function () { map.invalidateSize(); }, 100);
    window.addEventListener('resize', function () { map.invalidateSize(); });
}

// Expose globally
window.initializeRoutePlannerMap = initializeRoutePlannerMap;

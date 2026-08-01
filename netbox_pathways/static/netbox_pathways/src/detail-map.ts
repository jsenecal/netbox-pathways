/**
 * Reusable Leaflet map for detail pages and panels.
 *
 * Inline data format (passed directly):
 * {
 *   points:   [{ lat, lon, name, color, url, muted }],
 *   lines:    [{ coords: [[lon,lat],...], name, color, url }],
 *   polygons: [{ coords: [[lon,lat],...], lat, lon, name, color, url, muted }]
 * }
 *
 * Polygons are structure footprints: drawn as outlines at or above
 * `structurePolygonZoom`, and as a single icon at the carried centroid below
 * it.
 *
 * Also supports:
 * - Dynamic GeoJSON overlay layers fetched from the plugin API
 * - User-configured WMS/WMTS/tile overlay layers
 * - Layer control with toggleable overlays
 *
 * Config via window.PATHWAYS_CONFIG:
 * {
 *   maxNativeZoom: 19,
 *   apiBase: '/api/plugins/pathways/geo/',
 *   overlays: [
 *     { name: 'Layer Name', type: 'wms'|'wmts'|'tile', url: '...', ... }
 *   ]
 * }
 */

(function () {
    'use strict';

    // --- Local interfaces for inline data ---

    interface PointData {
        lat: number;
        lon: number;
        name: string;
        color?: string;
        url?: string;
        structure_type?: string;
        /** Context-only marker (e.g. the far end of a pathway leaving this
         *  page's subject); drawn faded so the subject's own plant reads first. */
        muted?: boolean;
    }

    interface LineData {
        coords: [number, number][];
        name: string;
        color?: string;
        url?: string;
    }

    /** A structure whose geometry is a footprint: outline plus its centroid,
     *  so the map can fall back to an icon when zoomed out. */
    interface PolygonData extends PointData {
        coords: [number, number][];
    }

    interface InlineData {
        points?: PointData[];
        lines?: LineData[];
        polygons?: PolygonData[];
    }

    interface InitGeoMapOptions {
        dynamicLayers?: boolean;
    }

    /** Extend HTMLElement to store the Leaflet map instance. */
    interface MapHTMLElement extends HTMLElement {
        _leafletMap?: L.Map;
    }

    // --- Config ---

    const CFG: Partial<PathwaysConfig> = window.PATHWAYS_CONFIG || {};
    const MAX_NATIVE_ZOOM: number = CFG.maxNativeZoom || 19;
    /** Zoom at or above which footprints draw as outlines rather than icons. */
    const STRUCTURE_POLYGON_ZOOM: number = CFG.structurePolygonZoom ?? 18;
    /** Zoom cap when fitting the initial view to the data. */
    const DEFAULT_FIT_ZOOM = 17;
    const API_BASE: string = CFG.apiBase || '/api/plugins/pathways/geo/';
    const USER_OVERLAYS: OverlayConfig[] = CFG.overlays || [];

    // --- Helpers ---

    function _escapeHtml(text: string): string {
        const el: HTMLSpanElement = document.createElement('span');
        el.textContent = text;
        return el.innerHTML;
    }

    function _makePopup(name: string, url?: string): string {
        let popup: string = '<strong>' + _escapeHtml(name) + '</strong>';
        if (url) {
            popup += '<br><a href="' + _escapeHtml(url) + '" class="btn btn-sm btn-primary mt-1">View</a>';
        }
        return popup;
    }

    function _getCookie(name: string): string | null {
        const value: string = '; ' + document.cookie;
        const parts: string[] = value.split('; ' + name + '=');
        if (parts.length === 2) return parts.pop()!.split(';').shift() || null;
        return null;
    }

    // --- Reset Control ---

    interface ResetHomeOptions extends L.ControlOptions {
        /** Zoom cap applied when the control refits the home bounds. */
        fitMaxZoom?: number;
    }

    interface ResetHomeConstructor {
        new(homeBounds: L.LatLngBounds, homeCenter: L.LatLng, homeZoom: number, opts?: ResetHomeOptions): L.Control;
    }

    const ResetHome: ResetHomeConstructor = L.Control.extend({
        options: { position: 'topleft' as const },

        initialize: function (
            this: any,
            homeBounds: L.LatLngBounds,
            homeCenter: L.LatLng,
            homeZoom: number,
            opts?: ResetHomeOptions,
        ) {
            this._homeBounds = homeBounds;
            this._homeCenter = homeCenter;
            this._homeZoom = homeZoom;
            L.Util.setOptions(this, opts);
        },

        onAdd: function (this: any): HTMLElement {
            const container: HTMLElement = L.DomUtil.create('div', 'leaflet-control-zoom leaflet-bar');
            const link: HTMLAnchorElement = L.DomUtil.create('a', '', container) as HTMLAnchorElement;
            link.href = '#';
            link.title = 'Reset view';
            link.setAttribute('role', 'button');
            link.setAttribute('aria-label', 'Reset view');
            const icon: HTMLElement = L.DomUtil.create('i', 'mdi mdi-crosshairs-gps', link);
            icon.style.fontSize = '16px';
            icon.style.lineHeight = '30px';

            L.DomEvent.disableClickPropagation(container);
            L.DomEvent.on(link, 'click', L.DomEvent.preventDefault);
            L.DomEvent.on(link, 'click', function (this: any) {
                if (this._homeBounds && this._homeBounds.isValid()) {
                    this._map.fitBounds(this._homeBounds, {
                        padding: [40, 40] as [number, number],
                        maxZoom: this.options.fitMaxZoom || DEFAULT_FIT_ZOOM,
                    });
                } else if (this._homeCenter) {
                    this._map.setView(this._homeCenter, this._homeZoom || 10);
                }
            }, this);

            return container;
        },
    }) as unknown as ResetHomeConstructor;

    // --- Base Layers ---

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
        let configs: BaseLayerDef[] = (CFG.baseLayers || []).filter(function (c: BaseLayerConfig): boolean { return !!c.url; });
        if (!configs.length) configs = DEFAULT_BASE_LAYERS;
        const layers: Record<string, L.TileLayer> = {};
        configs.forEach(function (cfg: BaseLayerDef) {
            const opts: L.TileLayerOptions = {
                attribution: cfg.attribution || '',
                maxNativeZoom: cfg.maxNativeZoom || MAX_NATIVE_ZOOM,
                maxZoom: 22,
                tileSize: cfg.tileSize || 256,
                zoomOffset: cfg.zoomOffset || 0,
            };
            layers[cfg.name] = L.tileLayer(cfg.url, opts);
        });
        return layers;
    }

    // --- User-configured Overlays (WMS/WMTS/tile) ---

    function _createUserOverlays(): Record<string, L.TileLayer | L.TileLayer.WMS> {
        const overlays: Record<string, L.TileLayer | L.TileLayer.WMS> = {};
        USER_OVERLAYS.forEach(function (cfg: OverlayConfig) {
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
                // tile or wmts — both use L.tileLayer with XYZ/WMTS URL template
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

    // --- Color & Icon Maps ---

    /** Opacity for context-only markers (see PointData.muted). Matches the
     *  edit widget's nearby-structures reference layer closely enough that the
     *  two read as the same "for context" treatment. */
    const MUTED_OPACITY = 0.45;

    const STRUCTURE_COLORS: Record<string, string> = {
        'Pole': '#2e7d32', 'Manhole': '#1565c0', 'Handhole': '#00838f',
        'Cabinet': '#e65100', 'Vault': '#6a1b9a', 'Pedestal': '#f9a825',
        'Building Entrance': '#c62828',
        'Tower': '#b71c1c', 'Rooftop': '#616161', 'Equipment Room': '#00796b',
        'Telecom Closet': '#283593', 'Riser Room': '#ad1457',
    };

    const STRUCTURE_SHAPES: Record<string, string> = {
        'Pole':               '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/><circle cx="10" cy="10" r="2.5"/>',
        'Manhole':            '<circle cx="10" cy="10" r="8"/>',
        'Handhole':           '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/>',
        'Cabinet':            '<rect x="2" y="2" width="16" height="16" rx="4"/>',
        'Vault':              '<rect x="2" y="2" width="16" height="16" rx="2"/>',
        'Pedestal':           '<rect x="3" y="3" width="14" height="14" rx="2" fill="none" stroke-width="2.5"/>',
        'Building Entrance':  '<rect x="3" y="3" width="14" height="14" rx="2" fill="none" stroke-width="2.5"/><circle cx="10" cy="10" r="2.5"/>',
        'Tower':              '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/><line x1="10" y1="2" x2="10" y2="18" stroke-width="1.5"/><line x1="2" y1="10" x2="18" y2="10" stroke-width="1.5"/>',
        'Rooftop':            '<polygon points="10,2 18,17 2,17"/>',
        'Equipment Room':     '<rect x="3" y="3" width="14" height="14" rx="4" fill="none" stroke-width="2.5"/>',
        'Telecom Closet':     '<rect x="3" y="3" width="10" height="10" rx="1" transform="rotate(45 10 10)"/>',
        'Riser Room':         '<rect x="3.5" y="3.5" width="9" height="9" rx="1" fill="none" stroke-width="2.5" transform="rotate(45 10 10)"/>',
    };

    const PATHWAY_COLORS: Record<string, string> = {
        'Conduit': '#795548', 'Aerial Span': '#1565c0', 'Direct Buried': '#616161',
        'Innerduct': '#e65100', 'Microduct': '#6a1b9a', 'Cable Tray': '#2e7d32',
        'Raceway': '#00838f', 'Submarine': '#1a237e',
    };

    function _structureIcon(type: string, size = 20): L.DivIcon {
        const color: string = STRUCTURE_COLORS[type] || '#616161';
        const shape: string = STRUCTURE_SHAPES[type] || '<circle cx="10" cy="10" r="8"/>';
        const isOutline: boolean = shape.includes('fill="none"');
        const half: number = size / 2;
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

    function _structurePointToLayer(feature: GeoJSON.Feature, latlng: L.LatLng): L.Marker {
        return L.marker(latlng, {
            icon: _structureIcon((feature.properties as Record<string, any>).structure_type),
        });
    }

    /** Footprint structures in the dynamic overlay keep their type color. */
    function _structureAreaStyle(feature?: GeoJSON.Feature): L.PathOptions {
        const type: string = (feature?.properties as Record<string, any>)?.structure_type;
        const color: string = STRUCTURE_COLORS[type] || '#616161';
        return { color: color, weight: 2, opacity: 0.9, fillColor: color, fillOpacity: 0.25 };
    }

    function _structurePopup(feature: GeoJSON.Feature, layer: L.Layer): void {
        const p = feature.properties as Record<string, any>;
        (layer as L.Marker).bindPopup(_makePopup(p.name, p.url));
    }

    function _pathwayStyle(feature?: GeoJSON.Feature): L.PathOptions {
        const color: string = PATHWAY_COLORS[(feature?.properties as Record<string, any>)?.pathway_type] || 'gray';
        return { color: color, weight: 4, opacity: 0.8 };
    }

    function _pathwayPopup(feature: GeoJSON.Feature, layer: L.Layer): void {
        const p = feature.properties as Record<string, any>;
        (layer as L.Polyline).bindPopup(_makePopup(p.name, p.url));
    }

    // --- Dynamic GeoJSON Loading ---

    function _fetchGeoJSON(endpoint: string, callback: (data: GeoJSON.FeatureCollection) => void): void {
        const url: string = API_BASE + endpoint + '?format=json&limit=1000';
        const xhr = new XMLHttpRequest();
        xhr.open('GET', url);
        xhr.setRequestHeader('Accept', 'application/json');
        const csrfToken: string | null = _getCookie('csrftoken');
        if (csrfToken) {
            xhr.setRequestHeader('X-CSRFToken', csrfToken);
        }
        xhr.onload = function (): void {
            if (xhr.status === 200) {
                try {
                    callback(JSON.parse(xhr.responseText));
                } catch (_e) {
                    // silently fail
                }
            }
        };
        xhr.send();
    }

    function loadDynamicLayers(map: L.Map, layerControl: L.Control.Layers): void {
        _fetchGeoJSON('structures/', function (data: GeoJSON.FeatureCollection) {
            const layer: L.GeoJSON = L.geoJSON(data, {
                pointToLayer: _structurePointToLayer,
                style: _structureAreaStyle,
                onEachFeature: _structurePopup,
            });
            layerControl.addOverlay(layer, 'Structures (all)');
        });

        _fetchGeoJSON('pathways/', function (data: GeoJSON.FeatureCollection) {
            const layer: L.GeoJSON = L.geoJSON(data, {
                style: _pathwayStyle,
                onEachFeature: _pathwayPopup,
            });
            layerControl.addOverlay(layer, 'Pathways (all)');
        });

        _fetchGeoJSON('conduits/', function (data: GeoJSON.FeatureCollection) {
            const layer: L.GeoJSON = L.geoJSON(data, {
                style: function (): L.PathOptions { return { color: 'brown', weight: 3, opacity: 0.7 }; },
                onEachFeature: _pathwayPopup,
            });
            layerControl.addOverlay(layer, 'Conduits');
        });

        _fetchGeoJSON('aerial-spans/', function (data: GeoJSON.FeatureCollection) {
            const layer: L.GeoJSON = L.geoJSON(data, {
                style: function (): L.PathOptions { return { color: 'blue', weight: 3, opacity: 0.7 }; },
                onEachFeature: _pathwayPopup,
            });
            layerControl.addOverlay(layer, 'Aerial Spans');
        });

        _fetchGeoJSON('direct-buried/', function (data: GeoJSON.FeatureCollection) {
            const layer: L.GeoJSON = L.geoJSON(data, {
                style: function (): L.PathOptions { return { color: 'gray', weight: 3, opacity: 0.7 }; },
                onEachFeature: _pathwayPopup,
            });
            layerControl.addOverlay(layer, 'Direct Buried');
        });
    }

    // --- Inline Data Rendering ---

    function _pointMarker(pt: PointData): L.Marker {
        const icon: L.DivIcon = pt.structure_type
            ? _structureIcon(pt.structure_type)
            : L.divIcon({
                className: 'pw-marker',
                html: '<svg class="pw-marker-svg" viewBox="0 0 20 20" width="28" height="28"' +
                      ' stroke="white" fill="' + (pt.color || '#1565c0') + '">' +
                      '<circle cx="10" cy="10" r="8"/></svg>',
                iconSize: [28, 28] as [number, number],
                iconAnchor: [14, 14] as [number, number],
                popupAnchor: [0, -16] as [number, number],
            });
        const marker: L.Marker = L.marker([pt.lat, pt.lon], {
            icon: icon,
            opacity: pt.muted ? MUTED_OPACITY : 1,
        });
        marker.bindPopup(_makePopup(pt.name, pt.url));
        return marker;
    }

    /**
     * Footprint structures: the outline at or above the footprint zoom, the
     * structure icon below it. Both layers are built once and swapped as the
     * user zooms, so a footprint is never invisible and never a smudge.
     */
    function _addPolygons(
        map: L.Map,
        polygons: PolygonData[],
        overlays: Record<string, L.LayerGroup>,
        bounds: L.LatLngBounds,
    ): void {
        const group: L.LayerGroup = L.layerGroup();
        const pairs = polygons.map(function (poly: PolygonData) {
            const latlngs: [number, number][] = poly.coords.map(
                function (c: [number, number]): [number, number] { return [c[1], c[0]]; },
            );
            const color: string = poly.color || '#1565c0';
            const shape: L.Polygon = L.polygon(latlngs, {
                color: color,
                weight: 2,
                opacity: poly.muted ? MUTED_OPACITY : 0.9,
                fillColor: color,
                fillOpacity: poly.muted ? MUTED_OPACITY / 2 : 0.25,
            });
            shape.bindPopup(_makePopup(poly.name, poly.url));
            latlngs.forEach(function (ll: [number, number]) { bounds.extend(ll); });
            bounds.extend([poly.lat, poly.lon]);
            return { shape: shape, marker: _pointMarker(poly) };
        });

        function sync(): void {
            const outlines: boolean = map.getZoom() >= STRUCTURE_POLYGON_ZOOM;
            pairs.forEach(function (pair) {
                group.removeLayer(outlines ? pair.marker : pair.shape);
                group.addLayer(outlines ? pair.shape : pair.marker);
            });
        }

        map.on('zoomend', sync);
        map.whenReady(sync);
        group.addTo(map);
        overlays['Footprints'] = group;
    }

    function _addInlineData(
        map: L.Map,
        data: InlineData,
        overlays: Record<string, L.LayerGroup>,
        bounds: L.LatLngBounds,
    ): void {
        if (data.points && data.points.length) {
            const pointsLayer: L.LayerGroup = L.layerGroup();
            data.points.forEach(function (pt: PointData) {
                _pointMarker(pt).addTo(pointsLayer);
                bounds.extend([pt.lat, pt.lon]);
            });
            pointsLayer.addTo(map);
            overlays['Points'] = pointsLayer;
        }

        if (data.lines && data.lines.length) {
            const linesLayer: L.LayerGroup = L.layerGroup();
            data.lines.forEach(function (line: LineData) {
                const latlngs: [number, number][] = line.coords.map(function (c: [number, number]): [number, number] { return [c[1], c[0]]; });
                const polyline: L.Polyline = L.polyline(latlngs, {
                    color: line.color || 'blue', weight: 4, opacity: 0.8,
                });
                polyline.bindPopup(_makePopup(line.name, line.url));
                polyline.addTo(linesLayer);
                latlngs.forEach(function (ll: [number, number]) { bounds.extend(ll); });
            });
            linesLayer.addTo(map);
            overlays['Lines'] = linesLayer;
        }

        if (data.polygons && data.polygons.length) {
            _addPolygons(map, data.polygons, overlays, bounds);
        }
    }

    // --- Main Entry Point ---

    /**
     * Initialize a map with inline data, layer control, and optional dynamic layers.
     *
     * @param containerId - DOM element ID for the map container
     * @param data - Inline data with points/lines arrays
     * @param options - Optional: { dynamicLayers: true }
     * @returns The Leaflet map instance, or undefined if container missing/already initialized
     */
    function initGeoMap(containerId: string, data: InlineData, options?: InitGeoMapOptions): L.Map | undefined {
        const container = document.getElementById(containerId) as MapHTMLElement | null;
        if (!container || container._leafletMap) return container?._leafletMap;

        options = options || {};

        const baseLayers: Record<string, L.TileLayer> = _createBaseLayers();
        const firstLayer: L.TileLayer = baseLayers[Object.keys(baseLayers)[0]];
        const map: L.Map = L.map(containerId, {
            scrollWheelZoom: true,
            layers: [firstLayer],
        });

        // Build overlay layers
        const overlayLayers: Record<string, L.LayerGroup> = {};
        const bounds: L.LatLngBounds = L.latLngBounds([]);

        // Inline data as togglable overlay groups
        _addInlineData(map, data, overlayLayers, bounds);

        // User-configured WMS/WMTS/tile overlays
        const userOverlays: Record<string, L.TileLayer | L.TileLayer.WMS> = _createUserOverlays();
        for (const name in userOverlays) {
            (overlayLayers as Record<string, L.Layer>)[name] = userOverlays[name];
        }

        // Layer control
        const layerControl: L.Control.Layers = L.control.layers(baseLayers, overlayLayers, {
            position: 'topright', collapsed: true,
        }).addTo(map);

        // Dynamic GeoJSON layers from API (fetched async, added to control)
        if (options.dynamicLayers) {
            loadDynamicLayers(map, layerControl);
        }

        // A footprint subject has to open zoomed in far enough to draw as an
        // outline, or the page about it shows a bare icon (#96).
        const fitMaxZoom: number = data.polygons && data.polygons.length
            ? Math.max(DEFAULT_FIT_ZOOM, STRUCTURE_POLYGON_ZOOM)
            : DEFAULT_FIT_ZOOM;

        // Set view
        if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [40, 40] as [number, number], maxZoom: fitMaxZoom });
        } else {
            map.setView([0, 0], 2);
        }

        // Reset control
        new ResetHome(bounds, map.getCenter(), map.getZoom(), { fitMaxZoom: fitMaxZoom }).addTo(map);

        container._leafletMap = map;
        return map;
    }

    // Expose globally
    (window as any).initGeoMap = initGeoMap;
    (window as any).loadDynamicLayers = loadDynamicLayers;
    (window as any)._createBaseLayers = _createBaseLayers;
    (window as any)._createUserOverlays = _createUserOverlays;

})();

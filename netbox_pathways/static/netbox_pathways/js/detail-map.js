/**
 * Reusable Leaflet map for detail pages and panels.
 *
 * Inline data format (passed directly):
 * {
 *   points: [{ lat, lon, name, color, url }],
 *   lines:  [{ coords: [[lon,lat],...], name, color, url }]
 * }
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

(function() {
    'use strict';

    var CFG = window.PATHWAYS_CONFIG || {};
    var MAX_NATIVE_ZOOM = CFG.maxNativeZoom || 19;
    var API_BASE = CFG.apiBase || '/api/plugins/pathways/geo/';
    var USER_OVERLAYS = CFG.overlays || [];

    // --- Helpers ---

    function _escapeHtml(text) {
        var el = document.createElement('span');
        el.textContent = text;
        return el.innerHTML;
    }

    function _makePopup(name, url) {
        var popup = '<strong>' + _escapeHtml(name) + '</strong>';
        if (url) {
            popup += '<br><a href="' + _escapeHtml(url) + '" class="btn btn-sm btn-primary mt-1">View</a>';
        }
        return popup;
    }

    function _getCookie(name) {
        var value = '; ' + document.cookie;
        var parts = value.split('; ' + name + '=');
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }

    // --- Reset Control ---

    L.Control.ResetHome = L.Control.extend({
        options: { position: 'topleft' },

        initialize: function(homeBounds, homeCenter, homeZoom, opts) {
            this._homeBounds = homeBounds;
            this._homeCenter = homeCenter;
            this._homeZoom = homeZoom;
            L.Util.setOptions(this, opts);
        },

        onAdd: function() {
            var container = L.DomUtil.create('div', 'leaflet-control-zoom leaflet-bar');
            var link = L.DomUtil.create('a', '', container);
            link.href = '#';
            link.title = 'Reset view';
            link.setAttribute('role', 'button');
            link.setAttribute('aria-label', 'Reset view');
            var icon = L.DomUtil.create('i', 'mdi mdi-crosshairs-gps', link);
            icon.style.fontSize = '16px';
            icon.style.lineHeight = '30px';

            L.DomEvent.disableClickPropagation(container);
            L.DomEvent.on(link, 'click', L.DomEvent.preventDefault);
            L.DomEvent.on(link, 'click', function() {
                if (this._homeBounds && this._homeBounds.isValid()) {
                    this._map.fitBounds(this._homeBounds, { padding: [40, 40], maxZoom: 17 });
                } else if (this._homeCenter) {
                    this._map.setView(this._homeCenter, this._homeZoom || 10);
                }
            }, this);

            return container;
        }
    });

    // --- Base Layers ---

    function _createBaseLayers() {
        return {
            'Street': L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap contributors',
                maxNativeZoom: MAX_NATIVE_ZOOM,
                maxZoom: 22
            }),
            'Satellite': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                attribution: 'Esri World Imagery',
                maxNativeZoom: 19,
                maxZoom: 22
            })
        };
    }

    // --- User-configured Overlays (WMS/WMTS/tile) ---

    function _createUserOverlays() {
        var overlays = {};
        USER_OVERLAYS.forEach(function(cfg) {
            var layer;
            if (cfg.type === 'wms') {
                layer = L.tileLayer.wms(cfg.url, {
                    layers: cfg.layers || '',
                    format: cfg.format || 'image/png',
                    transparent: cfg.transparent !== false,
                    attribution: cfg.attribution || '',
                    maxZoom: 22
                });
            } else {
                // tile or wmts — both use L.tileLayer with XYZ/WMTS URL template
                layer = L.tileLayer(cfg.url, {
                    attribution: cfg.attribution || '',
                    maxZoom: cfg.maxZoom || 22,
                    maxNativeZoom: cfg.maxNativeZoom || undefined
                });
            }
            overlays[cfg.name] = layer;
        });
        return overlays;
    }

    // --- GeoJSON Styling ---

    var STRUCTURE_COLORS = {
        'Pole': 'green', 'Manhole': 'blue', 'Handhole': 'cyan',
        'Cabinet': 'orange', 'Vault': 'purple', 'Pedestal': 'yellow',
        'Building Entrance': 'red', 'Splice Closure': 'brown',
        'Tower': 'darkred', 'Rooftop': 'gray', 'Equipment Room': 'teal',
        'Telecom Closet': 'indigo', 'Riser Room': 'pink'
    };

    var PATHWAY_COLORS = {
        'Conduit': 'brown', 'Aerial Span': 'blue', 'Direct Buried': 'gray',
        'Innerduct': 'orange', 'Microduct': 'purple', 'Cable Tray': 'green',
        'Raceway': 'cyan', 'Submarine': 'navy'
    };

    function _structurePointToLayer(feature, latlng) {
        var color = STRUCTURE_COLORS[feature.properties.structure_type] || 'gray';
        return L.circleMarker(latlng, {
            radius: 8, fillColor: color, color: '#000',
            weight: 1, opacity: 1, fillOpacity: 0.8
        });
    }

    function _structurePopup(feature, layer) {
        var p = feature.properties;
        layer.bindPopup(_makePopup(p.name, p.url));
    }

    function _pathwayStyle(feature) {
        var color = PATHWAY_COLORS[feature.properties.pathway_type] || 'gray';
        return { color: color, weight: 4, opacity: 0.8 };
    }

    function _pathwayPopup(feature, layer) {
        var p = feature.properties;
        layer.bindPopup(_makePopup(p.name, p.url));
    }

    // --- Dynamic GeoJSON Loading ---

    function _fetchGeoJSON(endpoint, callback) {
        var url = API_BASE + endpoint + '?format=json&limit=1000';
        var xhr = new XMLHttpRequest();
        xhr.open('GET', url);
        xhr.setRequestHeader('Accept', 'application/json');
        var csrfToken = _getCookie('csrftoken');
        if (csrfToken) {
            xhr.setRequestHeader('X-CSRFToken', csrfToken);
        }
        xhr.onload = function() {
            if (xhr.status === 200) {
                try {
                    callback(JSON.parse(xhr.responseText));
                } catch (e) {
                    // silently fail
                }
            }
        };
        xhr.send();
    }

    function loadDynamicLayers(map, layerControl) {
        _fetchGeoJSON('structures/', function(data) {
            var layer = L.geoJSON(data, {
                pointToLayer: _structurePointToLayer,
                onEachFeature: _structurePopup
            });
            layerControl.addOverlay(layer, 'Structures (all)');
        });

        _fetchGeoJSON('pathways/', function(data) {
            var layer = L.geoJSON(data, {
                style: _pathwayStyle,
                onEachFeature: _pathwayPopup
            });
            layerControl.addOverlay(layer, 'Pathways (all)');
        });

        _fetchGeoJSON('conduits/', function(data) {
            var layer = L.geoJSON(data, {
                style: function() { return { color: 'brown', weight: 3, opacity: 0.7 }; },
                onEachFeature: _pathwayPopup
            });
            layerControl.addOverlay(layer, 'Conduits');
        });

        _fetchGeoJSON('aerial-spans/', function(data) {
            var layer = L.geoJSON(data, {
                style: function() { return { color: 'blue', weight: 3, opacity: 0.7 }; },
                onEachFeature: _pathwayPopup
            });
            layerControl.addOverlay(layer, 'Aerial Spans');
        });

        _fetchGeoJSON('direct-buried/', function(data) {
            var layer = L.geoJSON(data, {
                style: function() { return { color: 'gray', weight: 3, opacity: 0.7 }; },
                onEachFeature: _pathwayPopup
            });
            layerControl.addOverlay(layer, 'Direct Buried');
        });
    }

    // --- Inline Data Rendering ---

    function _addInlineData(map, data, overlays, bounds) {
        if (data.points && data.points.length) {
            var pointsLayer = L.layerGroup();
            data.points.forEach(function(pt) {
                var marker = L.circleMarker([pt.lat, pt.lon], {
                    radius: 8, fillColor: pt.color || 'blue', color: '#000',
                    weight: 1, opacity: 1, fillOpacity: 0.8
                });
                marker.bindPopup(_makePopup(pt.name, pt.url));
                marker.addTo(pointsLayer);
                bounds.extend([pt.lat, pt.lon]);
            });
            pointsLayer.addTo(map);
            overlays['Points'] = pointsLayer;
        }

        if (data.lines && data.lines.length) {
            var linesLayer = L.layerGroup();
            data.lines.forEach(function(line) {
                var latlngs = line.coords.map(function(c) { return [c[1], c[0]]; });
                var polyline = L.polyline(latlngs, {
                    color: line.color || 'blue', weight: 4, opacity: 0.8
                });
                polyline.bindPopup(_makePopup(line.name, line.url));
                polyline.addTo(linesLayer);
                latlngs.forEach(function(ll) { bounds.extend(ll); });
            });
            linesLayer.addTo(map);
            overlays['Lines'] = linesLayer;
        }
    }

    // --- Main Entry Point ---

    /**
     * Initialize a map with inline data, layer control, and optional dynamic layers.
     *
     * @param {string} containerId - DOM element ID for the map container
     * @param {object} data - Inline data with points/lines arrays
     * @param {object} options - Optional: { dynamicLayers: true }
     * @returns {L.Map}
     */
    function initGeoMap(containerId, data, options) {
        var container = document.getElementById(containerId);
        if (!container || container._leafletMap) return container._leafletMap;

        options = options || {};

        var baseLayers = _createBaseLayers();
        var map = L.map(containerId, {
            scrollWheelZoom: true,
            layers: [baseLayers['Street']]
        });

        // Satellite-active toggle for dark mode CSS
        map.on('baselayerchange', function(e) {
            if (e.name === 'Satellite') {
                container.classList.add('satellite-active');
            } else {
                container.classList.remove('satellite-active');
            }
        });

        // Build overlay layers
        var overlayLayers = {};
        var bounds = L.latLngBounds();

        // Inline data as togglable overlay groups
        _addInlineData(map, data, overlayLayers, bounds);

        // User-configured WMS/WMTS/tile overlays
        var userOverlays = _createUserOverlays();
        for (var name in userOverlays) {
            overlayLayers[name] = userOverlays[name];
        }

        // Layer control
        var layerControl = L.control.layers(baseLayers, overlayLayers, {
            position: 'topright', collapsed: true
        }).addTo(map);

        // Dynamic GeoJSON layers from API (fetched async, added to control)
        if (options.dynamicLayers) {
            loadDynamicLayers(map, layerControl);
        }

        // Set view
        if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [40, 40], maxZoom: 17 });
        } else {
            map.setView([0, 0], 2);
        }

        // Reset control
        new L.Control.ResetHome(bounds, map.getCenter(), map.getZoom()).addTo(map);

        container._leafletMap = map;
        return map;
    }

    // Expose globally
    window.initGeoMap = initGeoMap;
    window.loadDynamicLayers = loadDynamicLayers;
    window._createBaseLayers = _createBaseLayers;
    window._createUserOverlays = _createUserOverlays;

})();

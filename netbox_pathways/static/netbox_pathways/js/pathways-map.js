/**
 * Full-page infrastructure map.
 *
 * Fetches structures and pathways from the GeoJSON API within the visible
 * bounding box, but only when zoomed in past a minimum threshold.
 * Re-fetches on pan/zoom with debouncing.
 */

(function() {
    'use strict';

    var CFG = window.PATHWAYS_CONFIG || {};
    var API_BASE = CFG.apiBase || '/api/plugins/pathways/geo/';
    var MAX_NATIVE_ZOOM = CFG.maxNativeZoom || 19;
    var MIN_DATA_ZOOM = 13;  // Don't fetch data below this zoom level

    // --- Color Maps ---

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

    // --- Helpers ---

    function _esc(text) {
        var el = document.createElement('span');
        el.textContent = text;
        return el.innerHTML;
    }

    function _getCookie(name) {
        var value = '; ' + document.cookie;
        var parts = value.split('; ' + name + '=');
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }

    function _bboxParam(map) {
        var b = map.getBounds();
        return b.getWest() + ',' + b.getSouth() + ',' + b.getEast() + ',' + b.getNorth();
    }

    function _fetchGeoJSON(endpoint, bbox, callback) {
        var url = API_BASE + endpoint + '?format=json&limit=2000&bbox=' + bbox;
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
                    // silently fail on parse error
                }
            }
        };
        xhr.send();
    }

    function _debounce(fn, delay) {
        var timer;
        return function() {
            clearTimeout(timer);
            timer = setTimeout(fn, delay);
        };
    }

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
        var userOverlays = (CFG.overlays || []);
        var overlays = {};
        userOverlays.forEach(function(cfg) {
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

    // --- Haversine distance (meters) ---

    function _haversine(lat1, lon1, lat2, lon2) {
        var R = 6371000;
        var p1 = lat1 * Math.PI / 180, p2 = lat2 * Math.PI / 180;
        var dp = (lat2 - lat1) * Math.PI / 180;
        var dl = (lon2 - lon1) * Math.PI / 180;
        var a = Math.sin(dp/2) * Math.sin(dp/2) +
                Math.cos(p1) * Math.cos(p2) * Math.sin(dl/2) * Math.sin(dl/2);
        return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    }

    // --- Zoom hint overlay ---

    function _createZoomHint(map) {
        var div = L.DomUtil.create('div', 'pathways-zoom-hint');
        div.style.cssText =
            'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);' +
            'z-index:800;padding:12px 24px;border-radius:8px;font-size:14px;' +
            'pointer-events:none;text-align:center;' +
            'background:rgba(0,0,0,0.7);color:#fff;';
        div.textContent = 'Zoom in to see infrastructure data';
        map.getContainer().appendChild(div);
        return div;
    }

    // --- Map Initialization ---

    function initializePathwaysMap(elementId, config) {
        var container = document.getElementById(elementId);

        var baseLayers = _createBaseLayers();
        var map = L.map(elementId, {
            layers: [baseLayers['Street']]
        }).setView(config.center, config.zoom);

        // Satellite-active toggle
        map.on('baselayerchange', function(e) {
            if (e.name === 'Satellite') {
                container.classList.add('satellite-active');
            } else {
                container.classList.remove('satellite-active');
            }
        });

        // Overlay layers
        var overlayLayers = {};

        // User-configured WMS/WMTS/tile overlays
        var userOverlays = _createUserOverlays();
        for (var name in userOverlays) {
            overlayLayers[name] = userOverlays[name];
        }

        // Layer control
        var layerControl = L.control.layers(baseLayers, overlayLayers, {
            position: 'topright', collapsed: false
        }).addTo(map);

        // Counters
        var structureCountEl = document.getElementById('structure-count');
        var pathwayCountEl = document.getElementById('pathway-count');
        var totalLengthEl = document.getElementById('total-length');

        // Zoom hint
        var zoomHint = _createZoomHint(map);

        // --- Dynamic data layers (re-fetched on move) ---

        var dataLayers = {
            structures: L.markerClusterGroup({
                maxClusterRadius: 50,
                spiderfyOnMaxZoom: true,
                disableClusteringAtZoom: 18
            }).addTo(map),
            pathways: L.layerGroup().addTo(map),
            conduits: L.layerGroup(),
            aerialSpans: L.layerGroup(),
            directBuried: L.layerGroup()
        };

        // Register in layer control
        layerControl.addOverlay(dataLayers.structures, 'Structures');
        layerControl.addOverlay(dataLayers.pathways, 'Pathways');
        layerControl.addOverlay(dataLayers.conduits, 'Conduits');
        layerControl.addOverlay(dataLayers.aerialSpans, 'Aerial Spans');
        layerControl.addOverlay(dataLayers.directBuried, 'Direct Buried');

        function _loadData() {
            var zoom = map.getZoom();

            if (zoom < MIN_DATA_ZOOM) {
                // Clear all data layers and show hint
                dataLayers.structures.clearLayers();
                dataLayers.pathways.clearLayers();
                dataLayers.conduits.clearLayers();
                dataLayers.aerialSpans.clearLayers();
                dataLayers.directBuried.clearLayers();
                zoomHint.style.display = '';
                if (structureCountEl) structureCountEl.textContent = '-';
                if (pathwayCountEl) pathwayCountEl.textContent = '-';
                if (totalLengthEl) totalLengthEl.textContent = '-';
                return;
            }

            zoomHint.style.display = 'none';
            var bbox = _bboxParam(map);

            // Structures
            if (map.hasLayer(dataLayers.structures)) {
                _fetchGeoJSON('structures/', bbox, function(data) {
                    dataLayers.structures.clearLayers();
                    L.geoJSON(data, {
                        pointToLayer: function(feature, latlng) {
                            var color = STRUCTURE_COLORS[feature.properties.structure_type] || 'gray';
                            return L.circleMarker(latlng, {
                                radius: 8, fillColor: color, color: '#000',
                                weight: 1, opacity: 1, fillOpacity: 0.8
                            });
                        },
                        onEachFeature: function(feature, layer) {
                            var p = feature.properties;
                            layer.bindPopup(
                                '<div class="pathways-popup">' +
                                '<h5>' + _esc(p.name) + '</h5>' +
                                '<table class="table table-sm">' +
                                '<tr><td><strong>Type:</strong></td><td>' + _esc(p.structure_type || '') + '</td></tr>' +
                                '<tr><td><strong>Site:</strong></td><td>' + _esc(p.site_name || '') + '</td></tr>' +
                                '</table></div>'
                            );
                        }
                    }).addTo(dataLayers.structures);
                    if (structureCountEl) {
                        structureCountEl.textContent = data.features ? data.features.length : 0;
                    }
                });
            }

            // Pathways
            if (map.hasLayer(dataLayers.pathways)) {
                _fetchGeoJSON('pathways/', bbox, function(data) {
                    dataLayers.pathways.clearLayers();
                    L.geoJSON(data, {
                        style: function(feature) {
                            return { color: PATHWAY_COLORS[feature.properties.pathway_type] || 'gray', weight: 3, opacity: 0.7 };
                        },
                        onEachFeature: function(feature, layer) {
                            var p = feature.properties;
                            layer.bindPopup(
                                '<div class="pathways-popup">' +
                                '<h5>' + _esc(p.name) + '</h5>' +
                                '<table class="table table-sm">' +
                                '<tr><td><strong>Type:</strong></td><td>' + _esc(p.pathway_type || '') + '</td></tr>' +
                                '<tr><td><strong>Cables:</strong></td><td>' + (p.cables_routed || 0) + '</td></tr>' +
                                '</table></div>'
                            );
                        }
                    }).addTo(dataLayers.pathways);
                    if (pathwayCountEl) {
                        pathwayCountEl.textContent = data.features ? data.features.length : 0;
                    }
                    if (totalLengthEl && data.features) {
                        var total = 0;
                        data.features.forEach(function(f) {
                            if (f.geometry && f.geometry.coordinates) {
                                var coords = f.geometry.coordinates;
                                for (var i = 0; i < coords.length - 1; i++) {
                                    total += _haversine(coords[i][1], coords[i][0], coords[i+1][1], coords[i+1][0]);
                                }
                            }
                        });
                        totalLengthEl.textContent = (total / 1000).toFixed(2);
                    }
                });
            }

            // Conduits
            if (map.hasLayer(dataLayers.conduits)) {
                _fetchGeoJSON('conduits/', bbox, function(data) {
                    dataLayers.conduits.clearLayers();
                    L.geoJSON(data, {
                        style: function() { return { color: 'brown', weight: 3, opacity: 0.7, dashArray: '5 5' }; },
                        onEachFeature: function(feature, layer) {
                            layer.bindPopup('<strong>' + _esc(feature.properties.name) + '</strong>');
                        }
                    }).addTo(dataLayers.conduits);
                });
            }

            // Aerial Spans
            if (map.hasLayer(dataLayers.aerialSpans)) {
                _fetchGeoJSON('aerial-spans/', bbox, function(data) {
                    dataLayers.aerialSpans.clearLayers();
                    L.geoJSON(data, {
                        style: function() { return { color: 'blue', weight: 3, opacity: 0.7, dashArray: '10 5' }; },
                        onEachFeature: function(feature, layer) {
                            layer.bindPopup('<strong>' + _esc(feature.properties.name) + '</strong>');
                        }
                    }).addTo(dataLayers.aerialSpans);
                });
            }

            // Direct Buried
            if (map.hasLayer(dataLayers.directBuried)) {
                _fetchGeoJSON('direct-buried/', bbox, function(data) {
                    dataLayers.directBuried.clearLayers();
                    L.geoJSON(data, {
                        style: function() { return { color: 'gray', weight: 3, opacity: 0.7, dashArray: '2 4' }; },
                        onEachFeature: function(feature, layer) {
                            layer.bindPopup('<strong>' + _esc(feature.properties.name) + '</strong>');
                        }
                    }).addTo(dataLayers.directBuried);
                });
            }
        }

        // Load data on move/zoom with debounce
        var debouncedLoad = _debounce(_loadData, 300);
        map.on('moveend', debouncedLoad);
        map.on('overlayadd', function() { _loadData(); });

        // Initial load
        _loadData();

        // Reset view button
        var resetBtn = document.getElementById('reset-view');
        if (resetBtn) {
            resetBtn.addEventListener('click', function() {
                map.setView(config.center, config.zoom);
            });
        }

        // Store reference
        window.PathwaysMap = {
            map: map,
            layerControl: layerControl
        };

        // Leaflet calculates size at init; force a recheck after layout settles
        setTimeout(function() { map.invalidateSize(); }, 100);
        window.addEventListener('resize', function() { map.invalidateSize(); });
    }

    window.initializePathwaysMap = initializePathwaysMap;

})();

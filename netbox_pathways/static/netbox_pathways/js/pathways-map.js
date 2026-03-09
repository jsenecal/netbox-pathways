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

(function() {
    'use strict';

    var CFG = window.PATHWAYS_CONFIG || {};
    var API_BASE = CFG.apiBase || '/api/plugins/pathways/geo/';
    var MAX_NATIVE_ZOOM = CFG.maxNativeZoom || 19;
    var MIN_DATA_ZOOM = 11;  // Don't fetch data below this zoom level

    // --- Color & Icon Maps ---

    var STRUCTURE_COLORS = {
        'pole': '#2e7d32', 'manhole': '#1565c0', 'handhole': '#00838f',
        'cabinet': '#e65100', 'vault': '#6a1b9a', 'pedestal': '#f9a825',
        'building_entrance': '#c62828', 'splice_closure': '#795548',
        'tower': '#b71c1c', 'roof': '#616161', 'equipment_room': '#00796b',
        'telecom_closet': '#283593', 'riser_room': '#ad1457'
    };

    var STRUCTURE_ICONS = {
        'pole': 'mdi-adjust',
        'manhole': 'mdi-checkbox-blank-circle',
        'handhole': 'mdi-checkbox-blank-circle-outline',
        'cabinet': 'mdi-square-rounded',
        'vault': 'mdi-square',
        'pedestal': 'mdi-square-outline',
        'building_entrance': 'mdi-square-dot',
        'splice_closure': 'mdi-set-center',
        'tower': 'mdi-target',
        'roof': 'mdi-triangle-outline',
        'equipment_room': 'mdi-square-rounded-outline',
        'telecom_closet': 'mdi-rhombus',
        'riser_room': 'mdi-rhombus-outline'
    };

    var PATHWAY_COLORS = {
        'conduit': '#795548', 'aerial': '#1565c0', 'direct_buried': '#616161',
        'innerduct': '#e65100', 'microduct': '#6a1b9a', 'tray': '#2e7d32',
        'raceway': '#00838f', 'submarine': '#1a237e'
    };

    function _structureIcon(type) {
        var color = STRUCTURE_COLORS[type] || '#616161';
        var icon = STRUCTURE_ICONS[type] || 'mdi-map-marker';
        return L.divIcon({
            className: 'pw-marker',
            html: '<div class="pw-marker-pin" style="background:' + color + '">' +
                  '<i class="mdi ' + icon + '"></i></div>',
            iconSize: [18, 18],
            iconAnchor: [9, 9],
            popupAnchor: [0, -10]
        });
    }

    function _clusterIcon(count) {
        // Match MarkerCluster's ring style: translucent outer + opaque inner
        var cls, size;
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
            iconSize: [size, size],
            iconAnchor: [size / 2, size / 2]
        });
    }

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

    // Track in-flight requests per endpoint so we can abort stale ones
    var _inflightXHR = {};

    function _fetchGeoJSON(endpoint, bbox, callback, extraParams) {
        // Abort any in-flight request for this endpoint
        if (_inflightXHR[endpoint]) {
            _inflightXHR[endpoint].abort();
        }
        var url = API_BASE + endpoint + '?format=json&bbox=' + bbox;
        if (extraParams) {
            for (var key in extraParams) {
                url += '&' + key + '=' + encodeURIComponent(extraParams[key]);
            }
        }
        var xhr = new XMLHttpRequest();
        _inflightXHR[endpoint] = xhr;
        xhr.open('GET', url);
        xhr.setRequestHeader('Accept', 'application/json');
        var csrfToken = _getCookie('csrftoken');
        if (csrfToken) {
            xhr.setRequestHeader('X-CSRFToken', csrfToken);
        }
        xhr.onload = function() {
            _inflightXHR[endpoint] = null;
            if (xhr.status === 200) {
                try {
                    callback(JSON.parse(xhr.responseText));
                } catch (e) {
                    // silently fail on parse error
                }
            }
        };
        xhr.onerror = function() { _inflightXHR[endpoint] = null; };
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

        // --- Layer visibility persistence (localStorage) ---

        var PREFS_KEY = 'pathways_map_layers';
        var DEFAULT_LAYERS = { 'Structures': true, 'Conduits': true, 'Aerial Spans': false, 'Direct Buried': false };

        function _loadPrefs() {
            try {
                var saved = localStorage.getItem(PREFS_KEY);
                return saved ? JSON.parse(saved) : null;
            } catch (e) { return null; }
        }

        function _savePrefs(layers) {
            try { localStorage.setItem(PREFS_KEY, JSON.stringify(layers)); } catch (e) { /* ignore */ }
        }

        var layerPrefs = _loadPrefs() || DEFAULT_LAYERS;

        // --- Dynamic data layers (re-fetched on move) ---

        // Structures wrapper — holds either server cluster markers or a MarkerCluster sub-group
        var structuresLayer = L.layerGroup();
        var markerClusterGroup = L.markerClusterGroup({
            maxClusterRadius: 35,
            spiderfyOnMaxZoom: true,
            disableClusteringAtZoom: 18
        });

        var dataLayers = {
            structures: structuresLayer,
            conduits: L.layerGroup(),
            aerialSpans: L.layerGroup(),
            directBuried: L.layerGroup()
        };

        var layerNames = {
            'Structures': dataLayers.structures,
            'Conduits': dataLayers.conduits,
            'Aerial Spans': dataLayers.aerialSpans,
            'Direct Buried': dataLayers.directBuried
        };

        // Add layers based on saved prefs
        for (var lname in layerNames) {
            if (layerPrefs[lname] !== false) {
                layerNames[lname].addTo(map);
            }
            layerControl.addOverlay(layerNames[lname], lname);
        }

        // Persist layer toggles
        map.on('overlayadd', function(e) {
            var prefs = _loadPrefs() || DEFAULT_LAYERS;
            prefs[e.name] = true;
            _savePrefs(prefs);
        });
        map.on('overlayremove', function(e) {
            var prefs = _loadPrefs() || DEFAULT_LAYERS;
            prefs[e.name] = false;
            _savePrefs(prefs);
        });

        function _loadData() {
            var zoom = map.getZoom();

            if (zoom < MIN_DATA_ZOOM) {
                structuresLayer.clearLayers();
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
            var pathwayCount = 0, totalLength = 0, pendingPathway = 0;

            function _updatePathwayStats() {
                if (pathwayCountEl) pathwayCountEl.textContent = pathwayCount;
                if (totalLengthEl) totalLengthEl.textContent = (totalLength / 1000).toFixed(2);
            }

            function _pathwayLoaded(data) {
                var count = data.features ? data.features.length : 0;
                pathwayCount += count;
                if (data.features) {
                    data.features.forEach(function(f) {
                        if (f.geometry && f.geometry.coordinates) {
                            var coords = f.geometry.coordinates;
                            for (var i = 0; i < coords.length - 1; i++) {
                                totalLength += _haversine(coords[i][1], coords[i][0], coords[i+1][1], coords[i+1][0]);
                            }
                        }
                    });
                }
                pendingPathway--;
                if (pendingPathway <= 0) _updatePathwayStats();
            }

            // Structures — send zoom for server-side clustering decision
            if (map.hasLayer(structuresLayer)) {
                _fetchGeoJSON('structures/', bbox, function(data) {
                    structuresLayer.clearLayers();
                    markerClusterGroup.clearLayers();

                    var isServerClustered = data.features && data.features.length > 0 &&
                                            data.features[0].properties.cluster;

                    if (isServerClustered) {
                        // Server-side clusters — render as plain markers (no client re-clustering)
                        var total = 0;
                        data.features.forEach(function(f) {
                            var count = f.properties.point_count;
                            total += count;
                            var latlng = L.latLng(f.geometry.coordinates[1], f.geometry.coordinates[0]);
                            var marker = L.marker(latlng, { icon: _clusterIcon(count) });
                            marker.bindPopup('<strong>' + count + ' structures</strong>');
                            structuresLayer.addLayer(marker);
                        });
                        if (structureCountEl) structureCountEl.textContent = total;
                    } else {
                        // Individual features — use client MarkerCluster for zoom 15-17
                        var geoLayer = L.geoJSON(data, {
                            pointToLayer: function(feature, latlng) {
                                return L.marker(latlng, {
                                    icon: _structureIcon(feature.properties.structure_type)
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
                        });
                        markerClusterGroup.addLayers(geoLayer.getLayers());
                        structuresLayer.addLayer(markerClusterGroup);
                        if (structureCountEl) {
                            structureCountEl.textContent = data.features ? data.features.length : 0;
                        }
                    }
                }, { zoom: zoom });
            }

            // Count how many pathway layers are active for stats
            pathwayCount = 0; totalLength = 0;
            pendingPathway = 0;
            if (map.hasLayer(dataLayers.conduits)) pendingPathway++;
            if (map.hasLayer(dataLayers.aerialSpans)) pendingPathway++;
            if (map.hasLayer(dataLayers.directBuried)) pendingPathway++;
            if (pendingPathway === 0) _updatePathwayStats();

            // Conduits
            if (map.hasLayer(dataLayers.conduits)) {
                _fetchGeoJSON('conduits/', bbox, function(data) {
                    dataLayers.conduits.clearLayers();
                    L.geoJSON(data, {
                        style: function() { return { color: '#795548', weight: 3, opacity: 0.7, dashArray: '5 5' }; },
                        onEachFeature: function(feature, layer) {
                            layer.bindPopup('<strong>' + _esc(feature.properties.name) + '</strong>');
                        }
                    }).addTo(dataLayers.conduits);
                    _pathwayLoaded(data);
                });
            }

            // Aerial Spans
            if (map.hasLayer(dataLayers.aerialSpans)) {
                _fetchGeoJSON('aerial-spans/', bbox, function(data) {
                    dataLayers.aerialSpans.clearLayers();
                    L.geoJSON(data, {
                        style: function() { return { color: '#1565c0', weight: 3, opacity: 0.7, dashArray: '10 5' }; },
                        onEachFeature: function(feature, layer) {
                            layer.bindPopup('<strong>' + _esc(feature.properties.name) + '</strong>');
                        }
                    }).addTo(dataLayers.aerialSpans);
                    _pathwayLoaded(data);
                });
            }

            // Direct Buried
            if (map.hasLayer(dataLayers.directBuried)) {
                _fetchGeoJSON('direct-buried/', bbox, function(data) {
                    dataLayers.directBuried.clearLayers();
                    L.geoJSON(data, {
                        style: function() { return { color: '#616161', weight: 3, opacity: 0.7, dashArray: '2 4' }; },
                        onEachFeature: function(feature, layer) {
                            layer.bindPopup('<strong>' + _esc(feature.properties.name) + '</strong>');
                        }
                    }).addTo(dataLayers.directBuried);
                    _pathwayLoaded(data);
                });
            }
        }

        // Load data on move/zoom with debounce
        var debouncedLoad = _debounce(_loadData, 500);
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

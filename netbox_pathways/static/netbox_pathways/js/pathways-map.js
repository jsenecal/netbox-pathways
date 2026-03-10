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

    function _titleCase(str) {
        return (str || '').replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });
    }

    // --- Sidebar Module ---

    var Sidebar = (function() {
        var _map = null;
        var _features = [];
        var _filtered = [];
        var _selected = null;
        var _activeTypes = {};  // type string -> boolean
        var _detailCache = {};
        var _highlightedLayer = null;
        var _highlightOutline = null;  // polyline shadow for pathway highlight

        function _colorForFeature(entry) {
            if (entry.featureType === 'structure') {
                return STRUCTURE_COLORS[entry.props.structure_type] || '#616161';
            }
            return PATHWAY_COLORS[entry.props.pathway_type] || '#616161';
        }

        function _typeKeyForFeature(entry) {
            if (entry.featureType === 'structure') {
                return entry.props.structure_type || 'unknown';
            }
            return entry.props.pathway_type || 'unknown';
        }

        function _featureId(entry) {
            return entry.featureType + '-' + (entry.props.id || '');
        }

        function init(map) {
            _map = map;

            var closeBtn = document.getElementById('pw-sidebar-close');
            if (closeBtn) {
                closeBtn.addEventListener('click', function() {
                    hide();
                });
            }

            var backBtn = document.getElementById('pw-detail-back');
            if (backBtn) {
                backBtn.addEventListener('click', function() {
                    showList();
                });
            }

            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') {
                    var detailPanel = document.getElementById('pw-panel-detail');
                    if (detailPanel && detailPanel.style.display !== 'none') {
                        showList();
                    } else {
                        hide();
                    }
                }
            });

            var searchInput = document.getElementById('pw-search');
            if (searchInput) {
                searchInput.addEventListener('input', _debounce(function() {
                    _applyFilters();
                }, 150));
            }

            map.on('click', function(e) {
                if (!e.originalEvent._sidebarClick) {
                    _unhighlightMapFeature();
                    _selected = null;
                    _highlightListItem(null);
                    var detailPanel = document.getElementById('pw-panel-detail');
                    if (detailPanel && detailPanel.style.display !== 'none') {
                        showList();
                    }
                }
            });
        }

        function show() {
            var listPanel = document.getElementById('pw-panel-list');
            if (listPanel) listPanel.style.display = '';
        }

        function hide() {
            _unhighlightMapFeature();
            _selected = null;
            var listPanel = document.getElementById('pw-panel-list');
            var detailPanel = document.getElementById('pw-panel-detail');
            if (listPanel) listPanel.style.display = 'none';
            if (detailPanel) detailPanel.style.display = 'none';
        }

        function setFeatures(features) {
            _features = features;
            // Cap cache size instead of clearing on every pan/zoom
            var cacheKeys = Object.keys(_detailCache);
            if (cacheKeys.length > 200) {
                cacheKeys.slice(0, 100).forEach(function(k) { delete _detailCache[k]; });
            }

            // Preserve selection across data reloads (e.g. panTo triggers moveend)
            if (_selected) {
                var selId = _featureId(_selected);
                var found = null;
                for (var i = 0; i < features.length; i++) {
                    if (_featureId(features[i]) === selId) {
                        found = features[i];
                        break;
                    }
                }
                if (found) {
                    _selected = found;
                    _highlightMapFeature(found);
                    _buildTypeFilters();
                    _applyFilters();
                    show();
                    return;  // keep detail panel open
                }
                _selected = null;
            }

            _buildTypeFilters();
            _applyFilters();
            if (features.length > 0) {
                show();
                showList();
            } else {
                hide();
            }
        }

        function showList() {
            var listPanel = document.getElementById('pw-panel-list');
            var detailPanel = document.getElementById('pw-panel-detail');
            if (listPanel) listPanel.style.display = '';
            if (detailPanel) detailPanel.style.display = 'none';
        }

        function showDetail(entry) {
            var listPanel = document.getElementById('pw-panel-list');
            var detailPanel = document.getElementById('pw-panel-detail');
            if (listPanel) listPanel.style.display = 'none';
            if (detailPanel) detailPanel.style.display = '';
            _renderDetail(entry);
        }

        function _unhighlightMapFeature() {
            if (_highlightOutline) {
                _highlightOutline.remove();
                _highlightOutline = null;
            }
            if (_highlightedLayer) {
                if (_highlightedLayer._origIcon) {
                    _highlightedLayer.setIcon(_highlightedLayer._origIcon);
                    delete _highlightedLayer._origIcon;
                }
                if (_highlightedLayer._origStyle && _highlightedLayer.setStyle) {
                    _highlightedLayer.setStyle(_highlightedLayer._origStyle);
                    delete _highlightedLayer._origStyle;
                }
                _highlightedLayer = null;
            }
        }

        function _highlightMapFeature(entry) {
            _unhighlightMapFeature();
            var layer = entry.layer;
            if (!layer) return;
            _highlightedLayer = layer;

            if (entry.featureType === 'structure') {
                // Marker — swap to a larger highlighted icon
                layer._origIcon = layer.getIcon();
                var type = entry.props.structure_type;
                var color = STRUCTURE_COLORS[type] || '#616161';
                var iconCls = STRUCTURE_ICONS[type] || 'mdi-map-marker';
                layer.setIcon(L.divIcon({
                    className: 'pw-marker pw-marker-selected',
                    html: '<div class="pw-marker-pin" style="background:' + color + '">' +
                          '<i class="mdi ' + iconCls + '"></i></div>',
                    iconSize: [26, 26],
                    iconAnchor: [13, 13],
                    popupAnchor: [0, -14]
                }));
            } else {
                // Polyline — add a thicker outline behind, then brighten the line
                var latlngs = layer.getLatLngs();
                if (latlngs && _map) {
                    var lineColor = _colorForFeature(entry);
                    _highlightOutline = L.polyline(latlngs, {
                        color: lineColor,
                        weight: 10,
                        opacity: 0.35,
                        interactive: false
                    }).addTo(_map);
                }
                layer._origStyle = {
                    weight: 3,
                    opacity: 0.7
                };
                layer.setStyle({ weight: 5, opacity: 1 });
            }
        }

        function selectFeature(entry) {
            _selected = entry;
            _highlightListItem(entry);
            _highlightMapFeature(entry);
            showDetail(entry);
            if (_map && entry.latlng) {
                var zoom = _map.getZoom();
                if (zoom < 16) {
                    _map.flyTo(entry.latlng, 17, { duration: 0.5 });
                } else {
                    _map.panTo(entry.latlng);
                }
            }
        }

        function _buildTypeFilters() {
            var container = document.getElementById('pw-type-filters');
            if (!container) return;
            container.textContent = '';

            // Collect unique types
            var typeMap = {};
            _features.forEach(function(entry) {
                var key = _typeKeyForFeature(entry);
                if (!typeMap[key]) {
                    typeMap[key] = _colorForFeature(entry);
                }
            });

            var types = Object.keys(typeMap).sort();
            if (types.length <= 1) return;  // No need for filters with 0-1 types

            // Initialize activeTypes for any new types (default active)
            types.forEach(function(t) {
                if (_activeTypes[t] === undefined) {
                    _activeTypes[t] = true;
                }
            });

            types.forEach(function(type) {
                var btn = document.createElement('button');
                btn.className = 'pw-filter-btn' + (_activeTypes[type] ? ' active' : '');
                btn.type = 'button';

                var dot = document.createElement('span');
                dot.className = 'pw-filter-dot';
                dot.style.background = typeMap[type];
                btn.appendChild(dot);

                var label = document.createTextNode(_titleCase(type));
                btn.appendChild(label);

                btn.addEventListener('click', function() {
                    _activeTypes[type] = !_activeTypes[type];
                    btn.classList.toggle('active', _activeTypes[type]);
                    _applyFilters();
                });

                container.appendChild(btn);
            });
        }

        function _applyFilters() {
            var searchInput = document.getElementById('pw-search');
            var query = (searchInput ? searchInput.value : '').toLowerCase().trim();

            _filtered = _features.filter(function(entry) {
                // Type filter
                var typeKey = _typeKeyForFeature(entry);
                if (_activeTypes[typeKey] === false) return false;

                // Search filter
                if (query) {
                    var name = (entry.props.name || '').toLowerCase();
                    var type = _titleCase(typeKey).toLowerCase();
                    if (name.indexOf(query) === -1 && type.indexOf(query) === -1) {
                        return false;
                    }
                }

                return true;
            });

            _renderList();
        }

        function _renderList() {
            var listEl = document.getElementById('pw-feature-list');
            var countEl = document.getElementById('pw-list-count');
            if (!listEl) return;

            listEl.textContent = '';

            if (countEl) countEl.textContent = _filtered.length;

            _filtered.forEach(function(entry) {
                var item = document.createElement('div');
                item.className = 'pw-list-item';
                item.setAttribute('data-feature-id', _featureId(entry));

                if (_selected && _featureId(_selected) === _featureId(entry)) {
                    item.classList.add('active');
                }

                var dot = document.createElement('span');
                dot.className = 'pw-list-dot';
                dot.style.background = _colorForFeature(entry);
                item.appendChild(dot);

                var label = document.createElement('span');
                label.className = 'pw-list-label';
                label.textContent = entry.props.name || 'Unnamed';
                label.title = entry.props.name || 'Unnamed';
                item.appendChild(label);

                var typeBadge = document.createElement('span');
                typeBadge.className = 'pw-list-type';
                typeBadge.textContent = _titleCase(_typeKeyForFeature(entry));
                item.appendChild(typeBadge);

                item.addEventListener('click', function() {
                    selectFeature(entry);
                });

                listEl.appendChild(item);
            });
        }

        function _highlightListItem(entry) {
            var listEl = document.getElementById('pw-feature-list');
            if (!listEl) return;
            var items = listEl.querySelectorAll('.pw-list-item');
            var targetId = entry ? _featureId(entry) : null;
            for (var i = 0; i < items.length; i++) {
                items[i].classList.toggle('active', items[i].getAttribute('data-feature-id') === targetId);
            }
        }

        function _renderDetail(entry) {
            var body = document.getElementById('pw-detail-body');
            if (!body) return;
            body.textContent = '';
            var p = entry.props;

            // Title with inline edit
            var titleRow = document.createElement('div');
            titleRow.style.cssText = 'display:flex;align-items:center;gap:6px;margin-bottom:8px;';

            var title = document.createElement('div');
            title.className = 'pw-detail-title';
            title.style.marginBottom = '0';
            title.textContent = p.name || 'Unnamed';
            titleRow.appendChild(title);

            var editBtn = document.createElement('button');
            editBtn.className = 'pw-edit-btn';
            editBtn.title = 'Edit name';
            var pencilIcon = document.createElement('i');
            pencilIcon.className = 'mdi mdi-pencil';
            editBtn.appendChild(pencilIcon);
            titleRow.appendChild(editBtn);

            body.appendChild(titleRow);

            // Inline edit form (hidden)
            var editForm = document.createElement('div');
            editForm.className = 'pw-inline-edit';
            var editInput = document.createElement('input');
            editInput.type = 'text';
            editInput.className = 'form-control form-control-sm';
            editInput.value = p.name || '';
            editInput.style.flex = '1';
            editForm.appendChild(editInput);

            var saveBtn = document.createElement('button');
            saveBtn.className = 'btn btn-sm btn-primary';
            saveBtn.textContent = 'Save';
            editForm.appendChild(saveBtn);

            var cancelEditBtn = document.createElement('button');
            cancelEditBtn.className = 'btn btn-sm btn-outline-secondary';
            cancelEditBtn.textContent = '\u00d7';
            editForm.appendChild(cancelEditBtn);

            body.appendChild(editForm);

            editBtn.addEventListener('click', function() {
                editForm.classList.add('active');
                titleRow.style.display = 'none';
                editInput.focus();
                editInput.select();
            });

            cancelEditBtn.addEventListener('click', function() {
                editForm.classList.remove('active');
                titleRow.style.display = '';
            });

            saveBtn.addEventListener('click', function() {
                var newName = editInput.value.trim();
                if (!newName || newName === p.name) {
                    cancelEditBtn.click();
                    return;
                }
                var url = _apiUrlForFeature(entry);
                var xhr = new XMLHttpRequest();
                xhr.open('PATCH', url);
                xhr.setRequestHeader('Content-Type', 'application/json');
                xhr.setRequestHeader('Accept', 'application/json');
                var csrfToken = _getCookie('csrftoken');
                if (csrfToken) xhr.setRequestHeader('X-CSRFToken', csrfToken);
                xhr.onload = function() {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        p.name = newName;
                        title.textContent = newName;
                        delete _detailCache[_featureId(entry)];
                        _applyFilters();
                    }
                    editForm.classList.remove('active');
                    titleRow.style.display = '';
                };
                xhr.send(JSON.stringify({ name: newName }));
            });

            editInput.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') saveBtn.click();
                if (e.key === 'Escape') cancelEditBtn.click();
            });

            // Type badge
            var color = _colorForFeature(entry);
            var typeKey = _typeKeyForFeature(entry);
            var badge = document.createElement('span');
            badge.className = 'pw-detail-badge';
            badge.style.background = color;
            badge.textContent = _titleCase(typeKey);
            body.appendChild(badge);

            // Basic attributes table from GeoJSON properties
            var table = document.createElement('table');
            table.className = 'pw-detail-table';
            var rows = [];
            if (entry.featureType === 'structure') {
                rows.push(['Type', _titleCase(p.structure_type)]);
                if (p.site_name) rows.push(['Site', p.site_name]);
            } else {
                rows.push(['Type', _titleCase(p.pathway_type)]);
            }

            rows.forEach(function(r) {
                var tr = document.createElement('tr');
                var tdLabel = document.createElement('td');
                tdLabel.textContent = r[0];
                var tdVal = document.createElement('td');
                tdVal.textContent = r[1];
                tr.appendChild(tdLabel);
                tr.appendChild(tdVal);
                table.appendChild(tr);
            });
            body.appendChild(table);

            // View link
            if (p.url) {
                var link = document.createElement('a');
                link.href = p.url;
                link.className = 'btn btn-sm btn-primary mb-3';
                var icon = document.createElement('i');
                icon.className = 'mdi mdi-open-in-new';
                link.appendChild(icon);
                link.appendChild(document.createTextNode(' View'));
                body.appendChild(link);
            }

            // Fetch enriched detail from REST API
            var detailContainer = document.createElement('div');
            body.appendChild(detailContainer);
            _fetchDetail(entry, detailContainer);
        }

        function _apiUrlForFeature(entry) {
            // Derive REST API URL from the HTML detail URL (entry.props.url)
            // e.g. /plugins/pathways/structures/5/ → /api/plugins/pathways/structures/5/
            if (entry.props.url) {
                return '/api' + entry.props.url;
            }
            // Fallback: construct from base
            var id = entry.props.id;
            var base = API_BASE.replace(/geo\/?$/, '');
            switch (entry.featureType) {
                case 'structure':
                    return base + 'structures/' + id + '/';
                case 'conduit':
                    return base + 'conduits/' + id + '/';
                case 'aerial':
                    return base + 'aerial-spans/' + id + '/';
                case 'direct_buried':
                    return base + 'direct-buried/' + id + '/';
                default:
                    return base + 'pathways/' + id + '/';
            }
        }

        function _fetchDetail(entry, container) {
            var cacheKey = _featureId(entry);
            if (_detailCache[cacheKey]) {
                _renderEnrichedDetail(_detailCache[cacheKey], entry, container);
                return;
            }

            var loadingDiv = document.createElement('div');
            loadingDiv.className = 'pw-detail-loading';
            loadingDiv.textContent = 'Loading details...';
            container.appendChild(loadingDiv);

            var url = _apiUrlForFeature(entry);
            var xhr = new XMLHttpRequest();
            xhr.open('GET', url);
            xhr.setRequestHeader('Accept', 'application/json');
            var csrfToken = _getCookie('csrftoken');
            if (csrfToken) {
                xhr.setRequestHeader('X-CSRFToken', csrfToken);
            }
            xhr.onload = function() {
                container.textContent = '';
                if (xhr.status === 200) {
                    try {
                        var data = JSON.parse(xhr.responseText);
                        _detailCache[cacheKey] = data;
                        _renderEnrichedDetail(data, entry, container);
                    } catch (e) {
                        var errDiv = document.createElement('div');
                        errDiv.className = 'pw-detail-loading';
                        errDiv.textContent = 'Error loading details';
                        container.appendChild(errDiv);
                    }
                } else {
                    var errDiv2 = document.createElement('div');
                    errDiv2.className = 'pw-detail-loading';
                    errDiv2.textContent = 'Could not load details (HTTP ' + xhr.status + ')';
                    container.appendChild(errDiv2);
                }
            };
            xhr.onerror = function() {
                container.textContent = '';
                var errDiv = document.createElement('div');
                errDiv.className = 'pw-detail-loading';
                errDiv.textContent = 'Network error';
                container.appendChild(errDiv);
            };
            xhr.send();
        }

        // --- Generic field value resolvers ---

        function _resolveValue(val) {
            // Returns { text, url } for any API value type
            if (val === null || val === undefined || val === '') return null;
            // Array — e.g. cables_routed: [{id, url, display}, ...]
            if (Array.isArray(val)) {
                if (val.length === 0) return null;
                var texts = [];
                for (var i = 0; i < val.length; i++) {
                    var r = _resolveValue(val[i]);
                    if (r) texts.push(r.text);
                }
                return texts.length > 0 ? { text: texts.join(', ') } : null;
            }
            // Choice field: {value, label}
            if (typeof val === 'object' && val !== null && val.label !== undefined) {
                return { text: val.label || _titleCase(val.value || '') };
            }
            // Nested FK: {id, url, display, ...}
            if (typeof val === 'object' && val !== null && (val.display || val.name || val.id !== undefined)) {
                return { text: val.display || val.name || String(val.id), url: val.url || null };
            }
            // Boolean
            if (val === true) return { text: 'Yes' };
            if (val === false) return { text: 'No' };
            // Primitive
            return { text: String(val) };
        }

        function _addFieldRow(table, label, val, suffix) {
            var resolved = _resolveValue(val);
            if (!resolved) return;
            var text = resolved.text + (suffix || '');
            var tr = document.createElement('tr');
            var tdLabel = document.createElement('td');
            tdLabel.textContent = label;
            var tdVal = document.createElement('td');
            if (resolved.url) {
                var a = document.createElement('a');
                a.href = resolved.url;
                a.textContent = text;
                tdVal.appendChild(a);
            } else {
                tdVal.textContent = text;
            }
            tr.appendChild(tdLabel);
            tr.appendChild(tdVal);
            table.appendChild(tr);
        }

        function _addTagsRow(table, tags) {
            if (!tags || !tags.length) return;
            var tr = document.createElement('tr');
            var tdLabel = document.createElement('td');
            tdLabel.textContent = 'Tags';
            var tdVal = document.createElement('td');
            tags.forEach(function(tag) {
                var badge = document.createElement('span');
                badge.className = 'badge';
                badge.style.cssText = 'margin-right:4px;margin-bottom:2px;';
                if (tag.color) {
                    badge.style.background = '#' + tag.color;
                    badge.style.color = '#fff';
                } else {
                    badge.style.background = 'var(--tblr-border-color-translucent, rgba(0,0,0,0.1))';
                }
                badge.textContent = tag.display || tag.name || tag;
                tdVal.appendChild(badge);
            });
            tr.appendChild(tdLabel);
            tr.appendChild(tdVal);
            table.appendChild(tr);
        }

        // Field definitions per feature type: [label, data_key, unit_suffix]
        var DETAIL_FIELDS = {
            structure: [
                ['Type', 'structure_type'],
                ['Site', 'site'],
                ['Elevation', 'elevation', ' m'],
                ['Height', 'height', ' m'],
                ['Width', 'width', ' m'],
                ['Length', 'length', ' m'],
                ['Depth', 'depth', ' m'],
                ['Tenant', 'tenant'],
                ['Installation Date', 'installation_date'],
                ['Access Notes', 'access_notes'],
                ['Comments', 'comments'],
            ],
            conduit: [
                ['Start Structure', 'start_structure'],
                ['End Structure', 'end_structure'],
                ['Start Location', 'start_location'],
                ['End Location', 'end_location'],
                ['Material', 'material'],
                ['Inner Diameter', 'inner_diameter', ' mm'],
                ['Outer Diameter', 'outer_diameter', ' mm'],
                ['Depth', 'depth', ' m'],
                ['Length', 'length', ' m'],
                ['Conduit Bank', 'conduit_bank'],
                ['Bank Position', 'bank_position'],
                ['Start Junction', 'start_junction'],
                ['End Junction', 'end_junction'],
                ['Cables Routed', 'cables_routed'],
                ['Tenant', 'tenant'],
                ['Installation Date', 'installation_date'],
                ['Comments', 'comments'],
            ],
            aerial: [
                ['Start Structure', 'start_structure'],
                ['End Structure', 'end_structure'],
                ['Start Location', 'start_location'],
                ['End Location', 'end_location'],
                ['Aerial Type', 'aerial_type'],
                ['Attachment Height', 'attachment_height', ' m'],
                ['Sag', 'sag', ' m'],
                ['Messenger Size', 'messenger_size'],
                ['Wind Loading', 'wind_loading'],
                ['Ice Loading', 'ice_loading'],
                ['Length', 'length', ' m'],
                ['Cables Routed', 'cables_routed'],
                ['Tenant', 'tenant'],
                ['Installation Date', 'installation_date'],
                ['Comments', 'comments'],
            ],
            direct_buried: [
                ['Start Structure', 'start_structure'],
                ['End Structure', 'end_structure'],
                ['Start Location', 'start_location'],
                ['End Location', 'end_location'],
                ['Burial Depth', 'burial_depth', ' m'],
                ['Warning Tape', 'warning_tape'],
                ['Tracer Wire', 'tracer_wire'],
                ['Armor Type', 'armor_type'],
                ['Length', 'length', ' m'],
                ['Cables Routed', 'cables_routed'],
                ['Tenant', 'tenant'],
                ['Installation Date', 'installation_date'],
                ['Comments', 'comments'],
            ]
        };
        // Default for unknown pathway types
        DETAIL_FIELDS['default'] = [
            ['Start Structure', 'start_structure'],
            ['End Structure', 'end_structure'],
            ['Start Location', 'start_location'],
            ['End Location', 'end_location'],
            ['Length', 'length', ' m'],
            ['Cables Routed', 'cables_routed'],
            ['Tenant', 'tenant'],
            ['Installation Date', 'installation_date'],
            ['Comments', 'comments'],
        ];

        function _renderEnrichedDetail(data, entry, container) {
            var fields = DETAIL_FIELDS[entry.featureType] || DETAIL_FIELDS['default'];
            var table = document.createElement('table');
            table.className = 'pw-detail-table';

            fields.forEach(function(f) {
                var val = data[f[1]];
                _addFieldRow(table, f[0], val, f[2] || '');
            });

            _addTagsRow(table, data.tags);

            if (table.childNodes.length > 0) {
                var heading = document.createElement('div');
                heading.style.fontWeight = '600';
                heading.style.fontSize = '0.85em';
                heading.style.marginBottom = '6px';
                heading.style.color = 'var(--tblr-muted-color, #667382)';
                heading.textContent = 'Details';
                container.appendChild(heading);
                container.appendChild(table);
            }

            // Timestamps
            if (data.created || data.last_updated) {
                var tsDiv = document.createElement('div');
                tsDiv.style.cssText = 'font-size:0.72em;color:var(--tblr-muted-color,#667382);margin-top:8px;';
                var parts = [];
                if (data.created) parts.push('Created ' + data.created.split('T')[0]);
                if (data.last_updated) parts.push('Updated ' + data.last_updated.split('T')[0]);
                tsDiv.textContent = parts.join(' · ');
                container.appendChild(tsDiv);
            }

            // For structures: show connected pathways
            if (entry.featureType === 'structure') {
                _renderConnectedPathways(entry, container);
            }
        }

        function _renderConnectedPathways(entry, container) {
            var structId = entry.props.id;
            // Match pathways whose cached detail references this structure
            var connected = _features.filter(function(f) {
                if (f.featureType === 'structure') return false;
                var cached = _detailCache[_featureId(f)];
                if (!cached) return false;
                var startId = cached.start_structure ? (cached.start_structure.id || cached.start_structure) : null;
                var endId = cached.end_structure ? (cached.end_structure.id || cached.end_structure) : null;
                return startId === structId || endId === structId;
            });
            if (connected.length === 0) return;

            var heading = document.createElement('div');
            heading.style.fontWeight = '600';
            heading.style.fontSize = '0.85em';
            heading.style.marginBottom = '6px';
            heading.style.marginTop = '12px';
            heading.style.color = 'var(--tblr-muted-color, #667382)';
            heading.textContent = 'Connected Pathways';
            container.appendChild(heading);

            connected.forEach(function(f) {
                var item = document.createElement('div');
                item.className = 'pw-list-item';
                item.style.padding = '6px 0';

                var dot = document.createElement('span');
                dot.className = 'pw-list-dot';
                dot.style.background = _colorForFeature(f);
                item.appendChild(dot);

                var label = document.createElement('span');
                label.className = 'pw-list-label';
                label.textContent = f.props.name || 'Unnamed';
                item.appendChild(label);

                var typeBadge = document.createElement('span');
                typeBadge.className = 'pw-list-type';
                typeBadge.textContent = _titleCase(_typeKeyForFeature(f));
                item.appendChild(typeBadge);

                item.addEventListener('click', function() {
                    selectFeature(f);
                });

                container.appendChild(item);
            });
        }

        return {
            init: init,
            show: show,
            hide: hide,
            setFeatures: setFeatures,
            showList: showList,
            showDetail: showDetail,
            selectFeature: selectFeature
        };
    })();

    // --- Hover Popover ---

    var Popover = {
        _el: null,
        _map: null,

        init: function(map) {
            this._map = map;
            this._el = document.createElement('div');
            this._el.className = 'pw-popover';
            this._el.style.display = 'none';
            map.getContainer().appendChild(this._el);
        },

        show: function(latlng, props) {
            var t = props.structure_type || props.pathway_type || '';
            this._el.textContent = '';

            var name = document.createElement('span');
            name.className = 'pw-popover-name';
            name.textContent = props.name || 'Unnamed';
            this._el.appendChild(name);

            if (t) {
                var type = document.createElement('span');
                type.className = 'pw-popover-type';
                type.textContent = _titleCase(t);
                this._el.appendChild(type);
            }

            this._position(latlng);
            this._el.style.display = '';
        },

        hide: function() {
            if (this._el) this._el.style.display = 'none';
        },

        _position: function(latlng) {
            var pt = this._map.latLngToContainerPoint(latlng);
            var cw = this._map.getContainer().clientWidth;
            var x = pt.x + 14;
            var y = pt.y - 10;
            if (x + 200 > cw) x = pt.x - 200;
            if (y < 0) y = pt.y + 20;
            this._el.style.left = x + 'px';
            this._el.style.top = y + 'px';
        }
    };

    // --- Pathway Line Labels ---

    function _addLineLabels(geoJsonLayer, layerGroup, map) {
        if (map.getZoom() < 15) return;

        geoJsonLayer.eachLayer(function(layer) {
            var coords = layer.getLatLngs();
            if (!coords || coords.length < 2) return;
            var name = layer.feature.properties.name;
            if (!name) return;

            var midIdx = Math.floor(coords.length / 2);
            var p1 = coords[midIdx - 1] || coords[0];
            var p2 = coords[midIdx];
            var midLat = (p1.lat + p2.lat) / 2;
            var midLng = (p1.lng + p2.lng) / 2;

            var dx = p2.lng - p1.lng;
            var dy = p2.lat - p1.lat;
            var angle = Math.atan2(dy, dx) * 180 / Math.PI;
            if (angle > 90) angle -= 180;
            if (angle < -90) angle += 180;

            var icon = L.divIcon({
                className: 'pw-line-label',
                html: '<div style="transform:rotate(' + (-angle) + 'deg)">' + _esc(name) + '</div>',
                iconSize: [0, 0],
                iconAnchor: [0, 0]
            });

            layerGroup.addLayer(L.marker([midLat, midLng], { icon: icon, interactive: false }));
        });
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

    var DEFAULT_BASE_LAYERS = [
        {
            name: 'Street',
            url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            attribution: '&copy; OpenStreetMap contributors',
            maxNativeZoom: MAX_NATIVE_ZOOM
        },
        {
            name: 'Satellite',
            url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attribution: 'Esri World Imagery',
            maxNativeZoom: 19
        }
    ];

    function _createBaseLayers() {
        var configured = (CFG.baseLayers || []).filter(function(c) { return !!c.url; });
        var configs = configured.length ? configured : DEFAULT_BASE_LAYERS;
        var layers = {};
        configs.forEach(function(cfg) {
            layers[cfg.name] = L.tileLayer(cfg.url, {
                attribution: cfg.attribution || '',
                maxNativeZoom: cfg.maxNativeZoom || MAX_NATIVE_ZOOM,
                maxZoom: 22,
                tileSize: cfg.tileSize || 256,
                zoomOffset: cfg.zoomOffset || 0
            });
        });
        return layers;
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
        var firstLayer = baseLayers[Object.keys(baseLayers)[0]];
        var map = L.map(elementId, {
            layers: [firstLayer]
        });

        // Fit to data extent if bounds provided, otherwise use center/zoom
        if (config.bounds) {
            map.fitBounds(config.bounds, { padding: [30, 30], maxZoom: 17 });
        } else {
            map.setView(config.center, config.zoom);
        }

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

        // Layer control (collapsed — overlays toggled from sidebar instead)
        var layerControl = L.control.layers(baseLayers, overlayLayers, {
            position: 'topright', collapsed: true
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

        // Add layers based on saved prefs (toggled from sidebar, not Leaflet control)
        for (var lname in layerNames) {
            if (layerPrefs[lname] !== false) {
                layerNames[lname].addTo(map);
            }
        }

        // Persist layer toggles
        map.on('overlayadd', function(e) {
            var prefs = _loadPrefs() || DEFAULT_LAYERS;
            prefs[e.name] = true;
            _savePrefs(prefs);
            _syncSidebarCheckbox(e.name, true);
        });
        map.on('overlayremove', function(e) {
            var prefs = _loadPrefs() || DEFAULT_LAYERS;
            prefs[e.name] = false;
            _savePrefs(prefs);
            _syncSidebarCheckbox(e.name, false);
        });

        // --- Sidebar layer toggles ---
        var _layerCheckboxes = {};

        function _syncSidebarCheckbox(name, checked) {
            if (_layerCheckboxes[name]) {
                _layerCheckboxes[name].checked = checked;
            }
        }

        function _buildSidebarLayerToggles() {
            var container = document.getElementById('pw-layer-toggles');
            if (!container) return;
            container.textContent = '';

            for (var lname in layerNames) {
                var label = document.createElement('label');
                label.className = 'pw-layer-toggle';

                var cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.checked = map.hasLayer(layerNames[lname]);
                _layerCheckboxes[lname] = cb;

                (function(name, checkbox) {
                    checkbox.addEventListener('change', function() {
                        if (checkbox.checked) {
                            map.addLayer(layerNames[name]);
                        } else {
                            map.removeLayer(layerNames[name]);
                        }
                        var prefs = _loadPrefs() || DEFAULT_LAYERS;
                        prefs[name] = checkbox.checked;
                        _savePrefs(prefs);
                        _loadData();
                    });
                })(lname, cb);

                label.appendChild(cb);
                label.appendChild(document.createTextNode(lname));

                container.appendChild(label);
            }
        }
        _buildSidebarLayerToggles();

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
                Sidebar.setFeatures([]);
                Sidebar.hide();
                return;
            }

            zoomHint.style.display = 'none';
            var bbox = _bboxParam(map);
            // Sidebar feature collection
            var allFeatures = [];
            var pendingLoads = 0;
            var totalExpectedLoads = 0;

            // Count active layers
            if (map.hasLayer(structuresLayer)) totalExpectedLoads++;
            if (map.hasLayer(dataLayers.conduits)) totalExpectedLoads++;
            if (map.hasLayer(dataLayers.aerialSpans)) totalExpectedLoads++;
            if (map.hasLayer(dataLayers.directBuried)) totalExpectedLoads++;

            // Pathway stats — count active pathway layers once
            var pathwayCount = 0, totalLength = 0;
            var pendingPathway = 0;
            if (map.hasLayer(dataLayers.conduits)) pendingPathway++;
            if (map.hasLayer(dataLayers.aerialSpans)) pendingPathway++;
            if (map.hasLayer(dataLayers.directBuried)) pendingPathway++;

            function _checkAllLoaded() {
                pendingLoads++;
                if (pendingLoads === totalExpectedLoads) {
                    Sidebar.setFeatures(allFeatures);
                }
            }

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
                            marker.on('click', function() {
                                map.setView(latlng, 15);
                            });
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
                                var entry = {
                                    props: feature.properties,
                                    featureType: 'structure',
                                    layer: layer,
                                    latlng: layer.getLatLng()
                                };
                                allFeatures.push(entry);
                                layer.on('click', function(e) {
                                    if (e.originalEvent) e.originalEvent._sidebarClick = true;
                                    Sidebar.selectFeature(entry);
                                });
                                layer.on('mouseover', function(e) {
                                    Popover.show(e.latlng || layer.getLatLng(), feature.properties);
                                });
                                layer.on('mouseout', function() { Popover.hide(); });
                            }
                        });
                        markerClusterGroup.addLayers(geoLayer.getLayers());
                        structuresLayer.addLayer(markerClusterGroup);
                        if (structureCountEl) {
                            structureCountEl.textContent = data.features ? data.features.length : 0;
                        }
                    }
                    _checkAllLoaded();
                }, { zoom: zoom });
            }

            if (pendingPathway === 0) _updatePathwayStats();

            // Shared pathway handler factory (C3 — deduplicate onEachFeature)
            function _makePathwayOpts(featureType, styleObj) {
                return {
                    style: function() { return styleObj; },
                    onEachFeature: function(feature, layer) {
                        var entry = {
                            props: feature.properties,
                            featureType: featureType,
                            layer: layer,
                            latlng: layer.getBounds().getCenter()
                        };
                        allFeatures.push(entry);
                        layer.on('click', function(e) {
                            if (e.originalEvent) e.originalEvent._sidebarClick = true;
                            Sidebar.selectFeature(entry);
                        });
                        layer.on('mouseover', function(e) { Popover.show(e.latlng, feature.properties); });
                        layer.on('mouseout', function() { Popover.hide(); });
                    }
                };
            }

            // Pathway layer configs: [endpoint, dataLayer, featureType, style]
            var pathwayConfigs = [
                ['conduits/', dataLayers.conduits, 'conduit', { color: '#795548', weight: 3, opacity: 0.7, dashArray: '5 5' }],
                ['aerial-spans/', dataLayers.aerialSpans, 'aerial', { color: '#1565c0', weight: 3, opacity: 0.7, dashArray: '10 5' }],
                ['direct-buried/', dataLayers.directBuried, 'direct_buried', { color: '#616161', weight: 3, opacity: 0.7, dashArray: '2 4' }]
            ];

            pathwayConfigs.forEach(function(cfg) {
                var endpoint = cfg[0], layer = cfg[1], ftype = cfg[2], style = cfg[3];
                if (!map.hasLayer(layer)) return;
                _fetchGeoJSON(endpoint, bbox, function(data) {
                    layer.clearLayers();
                    var geoLayer = L.geoJSON(data, _makePathwayOpts(ftype, style));
                    geoLayer.addTo(layer);
                    _addLineLabels(geoLayer, layer, map);
                    _pathwayLoaded(data);
                    _checkAllLoaded();
                });
            });

            // If no layers active, still update sidebar
            if (totalExpectedLoads === 0) {
                Sidebar.setFeatures([]);
            }
        }

        // Load data on move/zoom with debounce
        var debouncedLoad = _debounce(_loadData, 500);
        map.on('moveend', debouncedLoad);

        // Initialize sidebar and popover
        Sidebar.init(map);
        Popover.init(map);

        // Initial load
        _loadData();

        // Reset view button
        var resetBtn = document.getElementById('reset-view');
        if (resetBtn) {
            resetBtn.addEventListener('click', function() {
                if (config.bounds) {
                    map.fitBounds(config.bounds, { padding: [30, 30], maxZoom: 17 });
                } else {
                    map.setView(config.center, config.zoom);
                }
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

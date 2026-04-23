/**
 * Sidebar module for the full-page infrastructure map.
 *
 * Provides feature list, search/filter, detail panel with enriched
 * REST API data, inline name editing, and map feature highlighting.
 */

import type { FeatureEntry, FeatureType, DetailFieldDef, ResolvedValue, ServerSearchResult } from './types/features';
import { NATIVE_TYPES } from './types/features';
import { getLayerConfig } from './external-layers';

// ---------------------------------------------------------------------------
// Module-level helpers imported from the outer scope at init time
// ---------------------------------------------------------------------------

/** Set externally by pathways-map before Sidebar.init(). */
let _titleCase: (s: string) => string;
let _esc: (s: string) => string;
let _debounce: (fn: () => void, delay: number) => () => void;
let _getCookie: (name: string) => string | null;

let STRUCTURE_COLORS: Record<string, string>;
let STRUCTURE_SHAPES: Record<string, string>;
let PATHWAY_COLORS: Record<string, string>;
let API_BASE: string;

// ---------------------------------------------------------------------------
// Internal state
// ---------------------------------------------------------------------------

let _map: L.Map | null = null;
let _features: FeatureEntry[] = [];
let _filtered: FeatureEntry[] = [];
let _selected: FeatureEntry | null = null;
const _activeTypes: Record<string, boolean> = {};
const _detailCache: Record<string, Record<string, unknown>> = {};
let _highlightedLayer: (L.Marker & { _origIcon?: L.Icon | L.DivIcon }) | (L.Polyline & { _origStyle?: L.PathOptions }) | null = null;
let _highlightOutline: L.Polyline | null = null;
let _serverSearchCallback: ((query: string) => void) | null = null;
let _lastServerQuery = '';
let _pendingSelect: { url: string; featureType: string } | null = null;
let _pendingFlySelectId = '';
let _isKiosk = false;
let _onSelectionChange: (() => void) | null = null;
let _dimmedFeatures: FeatureEntry[] = [];
let _activeConnectedIds: Set<string> | null = null;
const DIM_OPACITY = 0.15;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function _isNativeType(featureType: string): boolean {
    return (NATIVE_TYPES as readonly string[]).indexOf(featureType) !== -1;
}

function _typeLabel(featureType: string): string {
    const extCfg = getLayerConfig(featureType);
    if (extCfg) return extCfg.label;
    return _titleCase(featureType.replace(/_/g, ' '));
}

function _colorForFeature(entry: FeatureEntry): string {
    if (entry.featureType === 'structure') {
        return STRUCTURE_COLORS[entry.props.structure_type || ''] || '#616161';
    }
    if (entry.featureType === 'circuit') {
        return '#d32f2f';
    }
    return PATHWAY_COLORS[entry.props.pathway_type || ''] || '#616161';
}

function _typeKeyForFeature(entry: FeatureEntry): string {
    if (entry.featureType === 'structure') {
        return (entry.props.structure_type as string) || 'unknown';
    }
    return (entry.props.pathway_type as string) || 'unknown';
}

function _featureId(entry: FeatureEntry): string {
    return entry.featureType + '-' + (entry.props.id || '');
}

/** Mix a hex colour toward white by `amount` (0 = original, 1 = white). */
function _lighten(hex: string, amount: number): string {
    const n = parseInt(hex.replace('#', ''), 16);
    const r = Math.round(((n >> 16) & 0xff) + (255 - ((n >> 16) & 0xff)) * amount);
    const g = Math.round(((n >> 8) & 0xff) + (255 - ((n >> 8) & 0xff)) * amount);
    const b = Math.round((n & 0xff) + (255 - (n & 0xff)) * amount);
    return '#' + ((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1);
}

// ---------------------------------------------------------------------------
// Highlight logic
// ---------------------------------------------------------------------------

function _unhighlightMapFeature(): void {
    if (_highlightOutline) {
        _highlightOutline.remove();
        _highlightOutline = null;
    }
    if (_highlightedLayer) {
        const layer = _highlightedLayer as Record<string, any>;
        if (layer._origIcon) {
            (layer as any).setIcon(layer._origIcon);
            delete layer._origIcon;
        }
        if (layer._origStyle && typeof (layer as any).setStyle === 'function') {
            (layer as any).setStyle(layer._origStyle);
            delete layer._origStyle;
        }
        _highlightedLayer = null;
    }
}

function _applyHighlightVisuals(entry: FeatureEntry): void {
    const layer = entry.layer;
    if (!layer) return;
    _highlightedLayer = layer as any;

    if (entry.featureType === 'structure') {
        const marker = layer as L.Marker & { _origIcon?: L.Icon | L.DivIcon };
        marker._origIcon = (marker as any).getIcon();
        const type = entry.props.structure_type || '';
        const color = STRUCTURE_COLORS[type] || '#616161';
        const shape = STRUCTURE_SHAPES[type] || '<circle cx="10" cy="10" r="8"/>';
        const isOutline = shape.includes('fill="none"');
        marker.setIcon(L.divIcon({
            className: 'pw-marker pw-marker-selected',
            html: '<svg class="pw-marker-svg" viewBox="0 0 20 20" width="26" height="26"' +
                  ' stroke="' + (isOutline ? color : 'white') +
                  '" fill="' + color + '">' + shape + '</svg>',
            iconSize: [26, 26] as [number, number],
            iconAnchor: [13, 13] as [number, number],
            popupAnchor: [0, -14] as [number, number],
        }));
    } else {
        const polyline = layer as L.Polyline & { _origStyle?: L.PathOptions };
        const origStyle = (polyline as any).options || {};
        polyline._origStyle = {
            weight: origStyle.weight || 3,
            opacity: origStyle.opacity || 0.7,
            color: origStyle.color,
            dashArray: origStyle.dashArray,
        };
        const latlngs = polyline.getLatLngs() as L.LatLng[];
        if (latlngs && latlngs.length > 0 && _map) {
            // Glow: lighten the feature's own color toward white
            _highlightOutline = L.polyline(latlngs, {
                color: _lighten(origStyle.color || '#888', 0.55),
                weight: 12,
                opacity: 0.5,
                interactive: false,
            }).addTo(_map);
        }
        polyline.setStyle({ weight: 6, opacity: 1, dashArray: '' });
    }
}

function _highlightMapFeature(entry: FeatureEntry): void {
    _unhighlightMapFeature();
    _applyHighlightVisuals(entry);
}

function _reapplyHighlight(entry: FeatureEntry): void {
    if (_highlightOutline) {
        _highlightOutline.remove();
        _highlightOutline = null;
    }
    _highlightedLayer = null;
    _applyHighlightVisuals(entry);
}

// ---------------------------------------------------------------------------
// Focus dimming — dim features not connected to the selected one
// ---------------------------------------------------------------------------

function _dimFeatures(connectedIds: Set<string>): void {
    _dimmedFeatures = [];
    _activeConnectedIds = connectedIds;
    _applyDim();
}

function _applyDim(): void {
    if (!_activeConnectedIds) return;
    _dimmedFeatures = [];
    _features.forEach(function (f: FeatureEntry) {
        const fid = _featureId(f);
        if (_activeConnectedIds!.has(fid)) return;
        if (_selected && fid === _featureId(_selected)) return;
        if (!f.layer) return;

        _dimmedFeatures.push(f);
        if (f.featureType === 'structure') {
            (f.layer as L.Marker).setOpacity(DIM_OPACITY);
        } else if (typeof (f.layer as L.Polyline).setStyle === 'function') {
            (f.layer as L.Polyline).setStyle({ opacity: DIM_OPACITY });
        }
    });
}

function _restoreDim(): void {
    _activeConnectedIds = null;
    _dimmedFeatures.forEach(function (f: FeatureEntry) {
        if (!f.layer) return;
        if (f.featureType === 'structure') {
            (f.layer as L.Marker).setOpacity(1);
        } else if (typeof (f.layer as L.Polyline).setStyle === 'function') {
            const orig = (f.layer as any)._origStyle;
            (f.layer as L.Polyline).setStyle({ opacity: orig ? orig.opacity : 0.7 });
        }
    });
    _dimmedFeatures = [];
}

// ---------------------------------------------------------------------------
// List rendering
// ---------------------------------------------------------------------------

function _highlightListItem(entry: FeatureEntry | null): void {
    const listEl = document.getElementById('pw-feature-list');
    if (!listEl) return;
    const items = listEl.querySelectorAll('.pw-list-item');
    const targetId = entry ? _featureId(entry) : null;
    for (let i = 0; i < items.length; i++) {
        items[i].classList.toggle('active', items[i].getAttribute('data-feature-id') === targetId);
    }
}

function _renderList(): void {
    const listEl = document.getElementById('pw-feature-list');
    const countEl = document.getElementById('pw-list-count');
    if (!listEl) return;

    listEl.textContent = '';
    if (countEl) {
        countEl.textContent = String(_filtered.length);
        countEl.style.display = _filtered.length > 0 ? '' : 'none';
    }

    _filtered.forEach(function (entry: FeatureEntry) {
        const item = document.createElement('div');
        item.className = 'pw-list-item';
        item.setAttribute('data-feature-id', _featureId(entry));

        if (_selected && _featureId(_selected) === _featureId(entry)) {
            item.classList.add('active');
        }

        const dot = document.createElement('span');
        dot.className = 'pw-list-dot';
        dot.style.background = _colorForFeature(entry);
        item.appendChild(dot);

        const label = document.createElement('span');
        label.className = 'pw-list-label';
        label.textContent = entry.props.name || 'Unnamed';
        label.title = entry.props.name || 'Unnamed';
        item.appendChild(label);

        const typeBadge = document.createElement('span');
        typeBadge.className = 'pw-list-type';
        typeBadge.textContent = _titleCase(_typeKeyForFeature(entry));
        item.appendChild(typeBadge);

        item.addEventListener('click', function () {
            selectFeature(entry);
        });

        listEl.appendChild(item);
    });
}

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

function _buildTypeFilters(): void {
    const container = document.getElementById('pw-type-filters');
    if (!container) return;
    container.textContent = '';

    const typeMap: Record<string, string> = {};
    _features.forEach(function (entry: FeatureEntry) {
        const key = _typeKeyForFeature(entry);
        if (!typeMap[key]) {
            typeMap[key] = _colorForFeature(entry);
        }
    });

    const types = Object.keys(typeMap).sort();
    if (types.length <= 1) return;

    types.forEach(function (t: string) {
        if (_activeTypes[t] === undefined) {
            _activeTypes[t] = true;
        }
    });

    types.forEach(function (type: string) {
        const btn = document.createElement('button');
        btn.className = 'pw-filter-btn' + (_activeTypes[type] ? ' active' : '');
        btn.type = 'button';

        const dot = document.createElement('span');
        dot.className = 'pw-filter-dot';
        dot.style.background = typeMap[type];
        btn.appendChild(dot);

        const label = document.createTextNode(_typeLabel(type));
        btn.appendChild(label);

        btn.addEventListener('click', function () {
            _activeTypes[type] = !_activeTypes[type];
            btn.classList.toggle('active', _activeTypes[type]);
            _applyFilters();
        });

        container.appendChild(btn);
    });
}

function _applyFilters(): void {
    const searchInput = document.getElementById('pw-search') as HTMLInputElement | null;
    const query = (searchInput ? searchInput.value : '').toLowerCase().trim();

    _filtered = _features.filter(function (entry: FeatureEntry) {
        const typeKey = _typeKeyForFeature(entry);
        if (_activeTypes[typeKey] === false) return false;

        if (query) {
            const name = (entry.props.name || '').toLowerCase();
            const type = _titleCase(typeKey).toLowerCase();
            if (name.indexOf(query) === -1 && type.indexOf(query) === -1) {
                return false;
            }
        }

        return true;
    });

    _renderList();

    // If no client-side results and there's a query, fall back to server search
    if (_filtered.length === 0 && query.length >= 2 && _serverSearchCallback) {
        if (query !== _lastServerQuery) {
            _lastServerQuery = query;
            _showSearchingIndicator();
            _serverSearchCallback(query);
        }
    } else {
        _lastServerQuery = '';
        _clearServerResults();
    }
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

/**
 * Build the UI detail-page URL for a native feature client-side.
 *
 * The GeoJSON geo endpoints intentionally omit a ``url`` property because
 * computing get_absolute_url() per row calls django.urls.reverse(), which
 * triggers lazy URL-pattern population (including the Strawberry GraphQL
 * schema). That single import adds ~12 s per 1000 features, making the
 * geo API unusably slow.  Building the URL here costs nothing.
 */
function _detailPageUrl(entry: FeatureEntry): string {
    const id = entry.props.id;
    if (!_isNativeType(entry.featureType) || id == null) return '';
    const base = '/plugins/pathways/';
    switch (entry.featureType) {
        case 'structure':     return base + 'structures/' + id + '/';
        case 'conduit_bank':  return base + 'conduit-banks/' + id + '/';
        case 'conduit':       return base + 'conduits/' + id + '/';
        case 'aerial':        return base + 'aerial-spans/' + id + '/';
        case 'direct_buried': return base + 'direct-buried/' + id + '/';
        case 'circuit':       return base + 'circuit-geometries/' + id + '/';
        default:              return base + 'pathways/' + id + '/';
    }
}

function _apiUrlForFeature(entry: FeatureEntry): string {
    if (entry.props.url) {
        return '/api' + entry.props.url;
    }
    const id = entry.props.id;

    // Native types use the pathways API
    if (_isNativeType(entry.featureType)) {
        const base = API_BASE.replace(/geo\/?$/, '');
        switch (entry.featureType) {
            case 'structure':
                return base + 'structures/' + id + '/';
            case 'conduit_bank':
                return base + 'conduit-banks/' + id + '/';
            case 'conduit':
                return base + 'conduits/' + id + '/';
            case 'aerial':
                return base + 'aerial-spans/' + id + '/';
            case 'direct_buried':
                return base + 'direct-buried/' + id + '/';
            case 'circuit':
                return base + 'circuit-geometries/' + id + '/';
            default:
                return base + 'pathways/' + id + '/';
        }
    }

    // Check external layer config for detail URL
    const extCfg = getLayerConfig(entry.featureType);
    if (extCfg?.detail?.urlTemplate) {
        return extCfg.detail.urlTemplate.replace('{id}', String(id));
    }
    return '';
}

// ---------------------------------------------------------------------------
// Value resolver
// ---------------------------------------------------------------------------

function _resolveValue(val: unknown): ResolvedValue | null {
    if (val === null || val === undefined || val === '') return null;

    // Array
    if (Array.isArray(val)) {
        if (val.length === 0) return null;
        const texts: string[] = [];
        for (let i = 0; i < val.length; i++) {
            const r = _resolveValue(val[i]);
            if (r) texts.push(r.text);
        }
        return texts.length > 0 ? { text: texts.join(', ') } : null;
    }

    // Choice field: {value, label}
    if (typeof val === 'object' && val !== null && 'label' in val) {
        const choice = val as { value?: string; label?: string };
        return { text: choice.label || _titleCase(choice.value || '') };
    }

    // Nested FK: {id, url, display_url, display, ...}
    if (typeof val === 'object' && val !== null) {
        const fk = val as { id?: number; url?: string; display_url?: string; display?: string; name?: string };
        if (fk.display || fk.name || fk.id !== undefined) {
            return { text: fk.display || fk.name || String(fk.id), url: fk.display_url || fk.url || null };
        }
    }

    // Boolean
    if (val === true) return { text: 'Yes' };
    if (val === false) return { text: 'No' };

    // Primitive
    return { text: String(val) };
}

function _addFieldRow(table: HTMLTableElement, label: string, val: unknown, suffix?: string): void {
    const resolved = _resolveValue(val);
    if (!resolved) return;
    const text = resolved.text + (suffix || '');
    const tr = document.createElement('tr');
    const tdLabel = document.createElement('td');
    tdLabel.textContent = label;
    const tdVal = document.createElement('td');
    if (resolved.url) {
        const a = document.createElement('a');
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

interface TagData {
    color?: string;
    display?: string;
    name?: string;
}

function _addTagsRow(table: HTMLTableElement, tags: TagData[] | undefined): void {
    if (!tags || !tags.length) return;
    const tr = document.createElement('tr');
    const tdLabel = document.createElement('td');
    tdLabel.textContent = 'Tags';
    const tdVal = document.createElement('td');
    tags.forEach(function (tag: TagData) {
        const badge = document.createElement('span');
        badge.className = 'badge';
        badge.style.cssText = 'margin-right:4px;margin-bottom:2px;';
        if (tag.color) {
            badge.style.background = '#' + tag.color;
            badge.style.color = '#fff';
        } else {
            badge.style.background = 'var(--tblr-border-color-translucent, rgba(0,0,0,0.1))';
        }
        badge.textContent = tag.display || tag.name || String(tag);
        tdVal.appendChild(badge);
    });
    tr.appendChild(tdLabel);
    tr.appendChild(tdVal);
    table.appendChild(tr);
}

// ---------------------------------------------------------------------------
// Detail field definitions
// ---------------------------------------------------------------------------

const DETAIL_FIELDS: Record<string, DetailFieldDef[]> = {
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
    conduit_bank: [
        ['Start Structure', 'start_structure'],
        ['End Structure', 'end_structure'],
        ['Start Face', 'start_face'],
        ['End Face', 'end_face'],
        ['Configuration', 'configuration'],
        ['Total Conduits', 'total_conduits'],
        ['Encasement', 'encasement_type'],
        ['Length', 'length', ' m'],
        ['Tenant', 'tenant'],
        ['Installation Date', 'installation_date'],
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
    ],
    circuit: [
        ['Circuit', 'circuit'],
        ['Provider Reference', 'provider_reference'],
        ['Comments', 'comments'],
    ],
    default: [
        ['Start Structure', 'start_structure'],
        ['End Structure', 'end_structure'],
        ['Start Location', 'start_location'],
        ['End Location', 'end_location'],
        ['Length', 'length', ' m'],
        ['Cables Routed', 'cables_routed'],
        ['Tenant', 'tenant'],
        ['Installation Date', 'installation_date'],
        ['Comments', 'comments'],
    ],
};

// ---------------------------------------------------------------------------
// Enriched detail rendering
// ---------------------------------------------------------------------------

/** Create a collapsible section with chevron toggle. */
function _createSection(title: string, parent: HTMLElement): HTMLElement {
    const header = document.createElement('div');
    header.className = 'pw-section-header';
    const chevron = document.createElement('i');
    chevron.className = 'mdi mdi-chevron-down';
    header.appendChild(chevron);
    const label = document.createElement('span');
    label.textContent = title;
    header.appendChild(label);
    parent.appendChild(header);

    const body = document.createElement('div');
    body.className = 'pw-section-body';
    parent.appendChild(body);

    header.addEventListener('click', function () {
        const collapsed = body.classList.toggle('collapsed');
        header.classList.toggle('collapsed', collapsed);
    });

    return body;
}

/** Add enrichment metric badges from API data to the badge row. */
function _addEnrichmentBadges(data: Record<string, unknown>, entry: FeatureEntry): void {
    const badgeRow = document.querySelector('.pw-metric-row');
    if (!badgeRow) return;

    // Add measurement badges based on feature type
    const metrics: [string, string, string][] = [];  // [label, field, suffix]

    if (entry.featureType === 'structure') {
        if (data.elevation) metrics.push(['Elev', 'elevation', ' m']);
    } else {
        if (data.length) metrics.push(['Length', 'length', ' m']);
    }

    if (entry.featureType === 'conduit') {
        if (data.inner_diameter) metrics.push(['ID', 'inner_diameter', ' mm']);
    }

    metrics.forEach(function (m) {
        const resolved = _resolveValue(data[m[1]]);
        if (!resolved) return;
        const badge = document.createElement('span');
        badge.className = 'pw-metric-badge pw-metric-muted';
        badge.textContent = m[0] + ' ' + resolved.text + m[2];
        badgeRow.appendChild(badge);
    });
}

function _renderEnrichedDetail(data: Record<string, unknown>, entry: FeatureEntry, container: HTMLElement): void {
    // Add metric badges from enriched data
    _addEnrichmentBadges(data, entry);

    // Check if this is an external layer feature
    const extCfg = getLayerConfig(entry.featureType);
    if (extCfg?.detail) {
        const sectionBody = _createSection('Details', container);
        const table = document.createElement('table');
        table.className = 'pw-detail-table';
        for (const fieldName of extCfg.detail.fields) {
            const val = data[fieldName];
            if (val !== undefined && val !== null) {
                _addFieldRow(table, _titleCase(fieldName.replace(/_/g, ' ')), val);
            }
        }
        sectionBody.appendChild(table);
        return;
    }

    const fields = DETAIL_FIELDS[entry.featureType] || DETAIL_FIELDS['default'];
    const table = document.createElement('table');
    table.className = 'pw-detail-table';

    fields.forEach(function (f: DetailFieldDef) {
        const val = data[f[1]];
        _addFieldRow(table, f[0], val, f[2] || '');
    });

    _addTagsRow(table, data.tags as TagData[] | undefined);

    if (table.childNodes.length > 0) {
        const sectionBody = _createSection('Details', container);
        sectionBody.appendChild(table);
    }

    // Timestamps
    if (data.created || data.last_updated) {
        const tsDiv = document.createElement('div');
        tsDiv.style.cssText = 'font-size:0.72em;color:var(--tblr-muted-color,#667382);margin-top:8px;';
        const parts: string[] = [];
        if (data.created) parts.push('Created ' + (data.created as string).split('T')[0]);
        if (data.last_updated) parts.push('Updated ' + (data.last_updated as string).split('T')[0]);
        tsDiv.textContent = parts.join(' \u00b7 ');
        container.appendChild(tsDiv);
    }

    // For structures: show connected pathways
    if (entry.featureType === 'structure') {
        _fetchConnectedPathways(entry, container);
    }
    // For pathways: show connected structures
    if (entry.featureType !== 'structure') {
        _renderConnectedStructures(data, entry, container);
    }
}

/**
 * Render a clickable list item for a connected object.
 *
 * @param selectId  Feature ID (e.g. "structure-123") used to look up in
 *                  viewport or navigate to if not found.
 * @param hintLatLng  Approximate location for flyTo when feature is off-screen.
 */
function _renderConnectedItem(
    parent: HTMLElement,
    name: string,
    color: string,
    typeLabel: string,
    mapFeature: FeatureEntry | undefined,
    selectId: string,
    hintLatLng?: { lat: number; lng: number },
): void {
    const item = document.createElement('div');
    item.className = 'pw-list-item';
    item.style.padding = '6px 0';
    item.style.cursor = 'pointer';

    const dot = document.createElement('span');
    dot.className = 'pw-list-dot';
    dot.style.background = color;
    item.appendChild(dot);

    const label = document.createElement('span');
    label.className = 'pw-list-label';
    label.textContent = name || 'Unnamed';
    item.appendChild(label);

    const badge = document.createElement('span');
    badge.className = 'pw-metric-badge pw-metric-muted';
    badge.style.fontSize = '0.65em';
    badge.style.padding = '1px 6px';
    badge.textContent = typeLabel;
    item.appendChild(badge);

    item.addEventListener('click', function () {
        // Re-check viewport — features may have been loaded since render
        const current = _features.find(function (f: FeatureEntry) {
            return _featureId(f) === selectId;
        });
        if (current) {
            selectFeature(current);
        } else if (hintLatLng && _map) {
            // Fly to approximate location; data reload will auto-select
            _pendingFlySelectId = selectId;
            _map.flyTo(hintLatLng as L.LatLngExpression, 18, { duration: 0.5 });
        } else {
            // No cached location — full page navigation
            window.location.href = window.location.pathname + '?select=' + encodeURIComponent(selectId);
        }
    });

    parent.appendChild(item);
}

/** Fetch connected pathways and neighbor structures for a structure. */
function _fetchConnectedPathways(entry: FeatureEntry, container: HTMLElement): void {
    const structId = entry.props.id;
    const base = API_BASE.replace(/geo\/?$/, '');
    const url = base + 'pathways/?structure_id=' + structId;

    const headers: Record<string, string> = { 'Accept': 'application/json' };
    const csrfToken = _getCookie('csrftoken');
    if (csrfToken) headers['X-CSRFToken'] = csrfToken;

    fetch(url, { headers }).then(function (resp) {
        return resp.ok ? resp.json() : null;
    }).then(function (data: { results?: Array<Record<string, unknown>> } | null) {
        if (!data || !data.results || data.results.length === 0) return;

        // Collect neighbor structures from pathway endpoints
        interface NeighborInfo { id: number; display: string; hint?: { lat: number; lng: number } }
        const neighborMap: Record<number, NeighborInfo> = {};
        const pwItems: Array<{ display: string; color: string; typeLabel: string; mapFeature: FeatureEntry | undefined; selectId: string; hint?: { lat: number; lng: number } }> = [];

        data.results.forEach(function (pw: Record<string, unknown>) {
            const pwType = pw.pathway_type as { value?: string; label?: string } | string || '';
            const typeKey = typeof pwType === 'object' ? (pwType.value || '') : pwType;
            const typeLabel = typeof pwType === 'object' ? (pwType.label || _titleCase(typeKey)) : _titleCase(typeKey);
            const color = PATHWAY_COLORS[typeKey] || '#616161';
            const display = (pw.display || pw.label || 'Unnamed') as string;

            const pwId = pw.id as number;
            const mapFeature = _features.find(function (f: FeatureEntry) {
                return f.featureType !== 'structure' && f.props.id === pwId;
            });
            pwItems.push({
                display, color, typeLabel, mapFeature,
                selectId: typeKey + '-' + pwId,
                hint: mapFeature ? mapFeature.latlng : undefined,
            });

            // Extract polyline endpoints for neighbor location hints
            let startHint: { lat: number; lng: number } | undefined;
            let endHint: { lat: number; lng: number } | undefined;
            if (mapFeature && mapFeature.layer) {
                try {
                    const latlngs = (mapFeature.layer as L.Polyline).getLatLngs() as L.LatLng[];
                    if (latlngs && latlngs.length >= 2) {
                        startHint = { lat: latlngs[0].lat, lng: latlngs[0].lng };
                        endHint = { lat: latlngs[latlngs.length - 1].lat, lng: latlngs[latlngs.length - 1].lng };
                    }
                } catch (_e) { /* not a polyline */ }
            }

            // Extract the "other" structure as a neighbor
            const startS = pw.start_structure as { id?: number; display?: string } | null;
            const endS = pw.end_structure as { id?: number; display?: string } | null;
            if (startS && startS.id && startS.id !== structId && !neighborMap[startS.id]) {
                neighborMap[startS.id] = { id: startS.id, display: startS.display || String(startS.id), hint: startHint };
            }
            if (endS && endS.id && endS.id !== structId && !neighborMap[endS.id]) {
                neighborMap[endS.id] = { id: endS.id, display: endS.display || String(endS.id), hint: endHint };
            }
        });

        // --- Connected Structures (neighbors) — listed first ---
        const neighbors = Object.values(neighborMap);
        if (neighbors.length > 0) {
            const structSection = _createSection(
                'Connected Structures (' + neighbors.length + ')',
                container,
            );
            neighbors.forEach(function (s) {
                const mf = _features.find(function (f: FeatureEntry) {
                    return f.featureType === 'structure' && f.props.id === s.id;
                });
                _renderConnectedItem(structSection, s.display, '#2e7d32', 'Structure',
                    mf, 'structure-' + s.id, s.hint,
                );
            });
        }

        // --- Connected Pathways ---
        const pwSection = _createSection(
            'Connected Pathways (' + pwItems.length + ')',
            container,
        );
        pwItems.forEach(function (item) {
            _renderConnectedItem(pwSection, item.display, item.color, item.typeLabel,
                item.mapFeature, item.selectId, item.hint,
            );
        });

        // Dim unrelated features
        const connectedIds = new Set<string>();
        neighbors.forEach(function (s) { connectedIds.add('structure-' + s.id); });
        pwItems.forEach(function (item) { connectedIds.add(item.selectId); });
        _dimFeatures(connectedIds);
    });
}

/** Render connected structures from the pathway's detail data. */
function _renderConnectedStructures(data: Record<string, unknown>, entry: FeatureEntry, container: HTMLElement): void {
    const structs: Array<{ id: number; display: string; url?: string }> = [];

    const startStruct = data.start_structure as { id?: number; display?: string; url?: string } | null;
    const endStruct = data.end_structure as { id?: number; display?: string; url?: string } | null;
    if (startStruct && startStruct.id) structs.push({
        id: startStruct.id,
        display: startStruct.display || String(startStruct.id),
        url: startStruct.url,
    });
    if (endStruct && endStruct.id && (!startStruct || endStruct.id !== startStruct.id)) structs.push({
        id: endStruct.id,
        display: endStruct.display || String(endStruct.id),
        url: endStruct.url,
    });

    if (structs.length === 0) return;

    const sectionBody = _createSection(
        'Connected Structures (' + structs.length + ')',
        container,
    );

    // Extract hint coordinates from the current pathway's endpoints
    let startHint: { lat: number; lng: number } | undefined;
    let endHint: { lat: number; lng: number } | undefined;
    if (entry.layer) {
        try {
            const latlngs = (entry.layer as L.Polyline).getLatLngs() as L.LatLng[];
            if (latlngs && latlngs.length >= 2) {
                startHint = { lat: latlngs[0].lat, lng: latlngs[0].lng };
                endHint = { lat: latlngs[latlngs.length - 1].lat, lng: latlngs[latlngs.length - 1].lng };
            }
        } catch (_e) { /* not a polyline */ }
    }

    structs.forEach(function (s, idx) {
        const mf = _features.find(function (f: FeatureEntry) {
            return f.featureType === 'structure' && f.props.id === s.id;
        });
        const hint = idx === 0 ? startHint : endHint;

        _renderConnectedItem(sectionBody, s.display, '#2e7d32', 'Structure',
            mf, 'structure-' + s.id, hint,
        );
    });

    // Dim unrelated features
    const connectedIds = new Set<string>();
    structs.forEach(function (s) { connectedIds.add('structure-' + s.id); });
    _dimFeatures(connectedIds);
}

// ---------------------------------------------------------------------------
// Detail fetch (async/await with fetch)
// ---------------------------------------------------------------------------

async function _fetchDetail(entry: FeatureEntry, container: HTMLElement): Promise<void> {
    const cacheKey = _featureId(entry);

    // Check for HTML fragment URL from external layer config
    const extCfg = getLayerConfig(entry.featureType);
    const htmlUrl = _resolveDetailUrl(extCfg, entry);

    if (htmlUrl) {
        // HTML fragment mode — check cache (stored as string under a prefixed key)
        const htmlCacheKey = 'html:' + cacheKey;
        if (_detailCache[htmlCacheKey]) {
            _setTrustedHtml(container, _detailCache[htmlCacheKey] as unknown as string);
            return;
        }
        await _fetchHtmlDetail(htmlUrl, htmlCacheKey, container);
        return;
    }

    // JSON mode — existing behavior
    if (_detailCache[cacheKey]) {
        _renderEnrichedDetail(_detailCache[cacheKey], entry, container);
        return;
    }

    const url = _apiUrlForFeature(entry);

    // No detail URL available — render GeoJSON properties directly
    if (!url) {
        const table = document.createElement('table');
        table.className = 'pw-detail-table';
        const props = entry.props as Record<string, unknown>;
        for (const key in props) {
            if (!props.hasOwnProperty(key)) continue;
            if (key === 'id' || key === 'url') continue;
            _addFieldRow(table, _titleCase(key.replace(/_/g, ' ')), props[key]);
        }
        container.appendChild(table);
        return;
    }

    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'pw-detail-loading';
    loadingDiv.textContent = 'Loading details...';
    container.appendChild(loadingDiv);
    const headers: Record<string, string> = { 'Accept': 'application/json' };
    const csrfToken = _getCookie('csrftoken');
    if (csrfToken) headers['X-CSRFToken'] = csrfToken;

    try {
        const response = await fetch(url, { headers });
        container.textContent = '';
        if (response.ok) {
            const data = await response.json() as Record<string, unknown>;
            _detailCache[cacheKey] = data;
            _renderEnrichedDetail(data, entry, container);
        } else {
            const errDiv = document.createElement('div');
            errDiv.className = 'pw-detail-loading';
            errDiv.textContent = 'Could not load details (HTTP ' + response.status + ')';
            container.appendChild(errDiv);
        }
    } catch (_e) {
        container.textContent = '';
        const errDiv = document.createElement('div');
        errDiv.className = 'pw-detail-loading';
        errDiv.textContent = 'Network error';
        container.appendChild(errDiv);
    }
}

/** Resolve HTML detail URL from external layer config, if available. */
function _resolveDetailUrl(
    extCfg: import('./types/external').ExternalLayerConfig | undefined,
    entry: FeatureEntry,
): string {
    if (!extCfg?.detail?.detailUrl) return '';
    return extCfg.detail.detailUrl.replace('{id}', String(entry.props.id));
}

/**
 * Inject trusted HTML into a container element.
 *
 * SECURITY: This HTML is fetched from same-origin endpoints served by
 * registered NetBox plugins — the same trust model as Django's
 * PluginTemplateExtension. Only installed plugin code can register
 * detail_url endpoints via the map layer registry.
 */
function _setTrustedHtml(container: HTMLElement, html: string): void {
    container.innerHTML = html;  // eslint-disable-line no-unsanitized/property
}

/** Fetch an HTML fragment and inject it into the container. */
async function _fetchHtmlDetail(
    url: string,
    cacheKey: string,
    container: HTMLElement,
): Promise<void> {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'pw-detail-loading';
    loadingDiv.textContent = 'Loading details...';
    container.appendChild(loadingDiv);

    const headers: Record<string, string> = { 'Accept': 'text/html' };
    const csrfToken = _getCookie('csrftoken');
    if (csrfToken) headers['X-CSRFToken'] = csrfToken;

    try {
        const response = await fetch(url, { headers });
        container.textContent = '';
        if (response.ok) {
            const html = await response.text();
            _detailCache[cacheKey] = html as unknown as Record<string, unknown>;
            _setTrustedHtml(container, html);
        } else {
            const errDiv = document.createElement('div');
            errDiv.className = 'pw-detail-loading';
            errDiv.textContent = 'Could not load details (HTTP ' + response.status + ')';
            container.appendChild(errDiv);
        }
    } catch (_e) {
        container.textContent = '';
        const errDiv = document.createElement('div');
        errDiv.className = 'pw-detail-loading';
        errDiv.textContent = 'Network error';
        container.appendChild(errDiv);
    }
}

// ---------------------------------------------------------------------------
// Detail panel rendering
// ---------------------------------------------------------------------------

function _renderDetail(entry: FeatureEntry): void {
    const body = document.getElementById('pw-detail-body');
    if (!body) return;
    body.textContent = '';
    const p = entry.props;

    // Title with inline edit
    const titleRow = document.createElement('div');
    titleRow.style.cssText = 'display:flex;align-items:center;gap:6px;margin-bottom:8px;';

    const title = document.createElement('div');
    title.className = 'pw-detail-title';
    title.style.marginBottom = '0';
    title.textContent = p.name || 'Unnamed';
    titleRow.appendChild(title);

    const editBtn = document.createElement('button');
    editBtn.className = 'pw-edit-btn';
    editBtn.title = 'Edit name';
    const pencilIcon = document.createElement('i');
    pencilIcon.className = 'mdi mdi-pencil';
    editBtn.appendChild(pencilIcon);
    titleRow.appendChild(editBtn);

    body.appendChild(titleRow);

    // Inline edit form (hidden)
    const editForm = document.createElement('div');
    editForm.className = 'pw-inline-edit';
    const editInput = document.createElement('input');
    editInput.type = 'text';
    editInput.className = 'form-control form-control-sm';
    editInput.value = p.name || '';
    editInput.style.flex = '1';
    editForm.appendChild(editInput);

    const saveBtn = document.createElement('button');
    saveBtn.className = 'btn btn-sm btn-primary';
    saveBtn.textContent = 'Save';
    editForm.appendChild(saveBtn);

    const cancelEditBtn = document.createElement('button');
    cancelEditBtn.className = 'btn btn-sm btn-outline-secondary';
    cancelEditBtn.textContent = '\u00d7';
    editForm.appendChild(cancelEditBtn);

    body.appendChild(editForm);

    editBtn.addEventListener('click', function () {
        editForm.classList.add('active');
        titleRow.style.display = 'none';
        editInput.focus();
        editInput.select();
    });

    cancelEditBtn.addEventListener('click', function () {
        editForm.classList.remove('active');
        titleRow.style.display = '';
    });

    saveBtn.addEventListener('click', function () {
        const newName = editInput.value.trim();
        if (!newName || newName === p.name) {
            cancelEditBtn.click();
            return;
        }
        const url = _apiUrlForFeature(entry);
        const patchHeaders: Record<string, string> = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        };
        const csrfToken = _getCookie('csrftoken');
        if (csrfToken) patchHeaders['X-CSRFToken'] = csrfToken;

        fetch(url, {
            method: 'PATCH',
            headers: patchHeaders,
            body: JSON.stringify({ name: newName }),
        }).then(function (response) {
            if (response.ok) {
                p.name = newName;
                title.textContent = newName;
                delete _detailCache[_featureId(entry)];
                _applyFilters();
            }
            editForm.classList.remove('active');
            titleRow.style.display = '';
        });
    });

    editInput.addEventListener('keydown', function (e: KeyboardEvent) {
        if (e.key === 'Enter') saveBtn.click();
        if (e.key === 'Escape') cancelEditBtn.click();
    });

    // Metric badge row
    const color = _colorForFeature(entry);
    const typeKey = _typeKeyForFeature(entry);
    const badgeRow = document.createElement('div');
    badgeRow.className = 'pw-metric-row';

    const typeBadge = document.createElement('span');
    typeBadge.className = 'pw-metric-badge';
    typeBadge.style.background = color;
    typeBadge.style.color = '#fff';
    typeBadge.textContent = _titleCase(typeKey);
    badgeRow.appendChild(typeBadge);

    if (entry.featureType === 'structure' && p.site_name) {
        const siteBadge = document.createElement('span');
        siteBadge.className = 'pw-metric-badge pw-metric-muted';
        siteBadge.textContent = p.site_name as string;
        badgeRow.appendChild(siteBadge);
    }

    body.appendChild(badgeRow);

    // View Details button
    const detailUrl = _detailPageUrl(entry);
    if (detailUrl) {
        const link = document.createElement('a');
        link.href = detailUrl;
        link.className = 'btn btn-sm btn-primary w-100 mb-3';
        const icon = document.createElement('i');
        icon.className = 'mdi mdi-open-in-new';
        link.appendChild(icon);
        link.appendChild(document.createTextNode(' View Details '));
        body.appendChild(link);
    }

    // Plan Route button (structures only)
    if (entry.featureType === 'structure') {
        const planLink = document.createElement('a');
        planLink.href = '/plugins/pathways/route-planner/?start=' + p.id;
        planLink.className = 'btn btn-sm btn-outline-primary w-100 mb-3';
        const planIcon = document.createElement('i');
        planIcon.className = 'mdi mdi-map-search-outline';
        planLink.appendChild(planIcon);
        planLink.appendChild(document.createTextNode(' Plan Route From Here'));
        body.appendChild(planLink);
    }

    // Fetch enriched detail from REST API
    const detailContainer = document.createElement('div');
    body.appendChild(detailContainer);
    _fetchDetail(entry, detailContainer);
}

// ---------------------------------------------------------------------------
// Server-side search fallback
// ---------------------------------------------------------------------------

function _showSearchingIndicator(): void {
    const listEl = document.getElementById('pw-feature-list');
    if (!listEl) return;
    const indicator = document.createElement('div');
    indicator.className = 'pw-server-search-status';
    indicator.id = 'pw-server-searching';
    const icon = document.createElement('i');
    icon.className = 'mdi mdi-magnify mdi-spin';
    indicator.appendChild(icon);
    indicator.appendChild(document.createTextNode(' Searching all features\u2026'));
    listEl.appendChild(indicator);
}

function _clearServerResults(): void {
    const el = document.getElementById('pw-server-searching');
    if (el) el.remove();
    const hdr = document.getElementById('pw-server-results-header');
    if (hdr) hdr.remove();
    const items = document.querySelectorAll('.pw-server-result');
    for (let i = 0; i < items.length; i++) items[i].remove();
}

function setServerResults(results: ServerSearchResult[]): void {
    // Remove the "searching" indicator
    const searching = document.getElementById('pw-server-searching');
    if (searching) searching.remove();

    const listEl = document.getElementById('pw-feature-list');
    if (!listEl) return;

    // Remove any previous server results
    const oldHdr = document.getElementById('pw-server-results-header');
    if (oldHdr) oldHdr.remove();
    const oldItems = document.querySelectorAll('.pw-server-result');
    for (let i = 0; i < oldItems.length; i++) oldItems[i].remove();

    if (results.length === 0) {
        const noResults = document.createElement('div');
        noResults.className = 'pw-server-search-status pw-server-result';
        noResults.textContent = 'No matching features found.';
        listEl.appendChild(noResults);
        return;
    }

    const header = document.createElement('div');
    header.id = 'pw-server-results-header';
    header.className = 'pw-server-search-status';
    const hdrIcon = document.createElement('i');
    hdrIcon.className = 'mdi mdi-earth';
    header.appendChild(hdrIcon);
    header.appendChild(document.createTextNode(
        ' ' + results.length + ' result' + (results.length !== 1 ? 's' : '') + ' outside current view'
    ));
    listEl.appendChild(header);

    results.forEach(function (result: ServerSearchResult) {
        const item = document.createElement('div');
        item.className = 'pw-list-item pw-server-result';

        const dot = document.createElement('span');
        dot.className = 'pw-list-dot';
        const color = result.featureType === 'structure'
            ? (STRUCTURE_COLORS[result.typeKey] || '#616161')
            : (PATHWAY_COLORS[result.typeKey] || '#616161');
        dot.style.background = color;
        item.appendChild(dot);

        const label = document.createElement('span');
        label.className = 'pw-list-label';
        label.textContent = result.name || 'Unnamed';
        label.title = result.name || 'Unnamed';
        item.appendChild(label);

        const typeBadge = document.createElement('span');
        typeBadge.className = 'pw-list-type';
        typeBadge.textContent = _titleCase(result.typeKey);
        item.appendChild(typeBadge);

        const goIcon = document.createElement('i');
        goIcon.className = 'mdi mdi-crosshairs-gps';
        goIcon.style.cssText = 'color:var(--tblr-muted-color,#667382);flex-shrink:0;';
        goIcon.title = 'Go to location';
        item.appendChild(goIcon);

        item.addEventListener('click', function () {
            if (_map) {
                if (result.url) {
                    _pendingSelect = { url: result.url, featureType: result.featureType };
                }
                _map.flyTo(result.latlng, 18, { duration: 0.8 });
            }
        });

        listEl.appendChild(item);
    });
}

function onServerSearch(cb: (query: string) => void): void {
    _serverSearchCallback = cb;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

function init(map: L.Map, kiosk?: boolean): void {
    _isKiosk = !!kiosk;
    _map = map;

    const toggleBtn = document.getElementById('pw-sidebar-toggle');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', function () {
            _setListBodyVisible(_isCollapsed());
        });
    }

    const backBtn = document.getElementById('pw-detail-back');
    if (backBtn) {
        backBtn.addEventListener('click', function () {
            showList();
        });
    }

    document.addEventListener('keydown', function (e: KeyboardEvent) {
        if (e.key === 'Escape') {
            const detailPanel = document.getElementById('pw-panel-detail');
            if (detailPanel && detailPanel.style.display !== 'none') {
                showList();
            }
            _unhighlightMapFeature();
            _restoreDim();
            _selected = null;
            _highlightListItem(null);
            if (_isKiosk) _kioskSidebarClose();
            if (_onSelectionChange) _onSelectionChange();
        }
    });

    const searchInput = document.getElementById('pw-search');
    if (searchInput) {
        searchInput.addEventListener('input', _debounce(function () {
            _applyFilters();
        }, 150));
    }

    map.on('click', function (e: L.LeafletMouseEvent) {
        if (!(e.originalEvent as any)._sidebarClick) {
            _unhighlightMapFeature();
            _restoreDim();
            _selected = null;
            _highlightListItem(null);
            const detailPanel = document.getElementById('pw-panel-detail');
            if (detailPanel && detailPanel.style.display !== 'none') {
                showList();
            }
            if (_onSelectionChange) _onSelectionChange();
        }
    });

    if (_isKiosk) {
        const kioskCloseBtn = document.getElementById('pw-kiosk-close');
        if (kioskCloseBtn) {
            kioskCloseBtn.addEventListener('click', function () {
                _kioskSidebarClose();
                const detailPanel = document.getElementById('pw-panel-detail');
                if (detailPanel) detailPanel.style.display = 'none';
            });
        }
        document.addEventListener('keydown', function (e: KeyboardEvent) {
            if (e.key === 'Escape') {
                _kioskSidebarClose();
                const detailPanel = document.getElementById('pw-panel-detail');
                if (detailPanel) detailPanel.style.display = 'none';
            }
        });
    }
}

function _setListBodyVisible(visible: boolean): void {
    const body = document.getElementById('pw-panel-list-body');
    const chevron = document.getElementById('pw-sidebar-chevron');
    if (body) body.classList.toggle('collapsed', !visible);
    if (chevron) chevron.classList.toggle('collapsed', !visible);
}

function _kioskSidebarOpen(): void {
    const sidebar = document.getElementById('pw-sidebar');
    if (!sidebar) return;
    sidebar.classList.add('pw-sidebar-open');
}

function _kioskSidebarClose(): void {
    const sidebar = document.getElementById('pw-sidebar');
    if (!sidebar) return;
    sidebar.classList.remove('pw-sidebar-open');
}

function _isCollapsed(): boolean {
    const body = document.getElementById('pw-panel-list-body');
    return body ? body.classList.contains('collapsed') : false;
}

function show(): void {
    if (_isKiosk) {
        _kioskSidebarOpen();
        return;
    }
    const sidebar = document.getElementById('pw-sidebar');
    if (sidebar) sidebar.classList.remove('pw-sidebar-hidden');
    _setListBodyVisible(true);
}

function hide(): void {
    if (_isKiosk) { _kioskSidebarClose(); return; }
    const sidebar = document.getElementById('pw-sidebar');
    if (sidebar) sidebar.classList.add('pw-sidebar-hidden');
}

function setFeatures(features: FeatureEntry[]): void {
    _features = features;
    // Cap cache size instead of clearing on every pan/zoom
    const cacheKeys = Object.keys(_detailCache);
    if (cacheKeys.length > 200) {
        cacheKeys.slice(0, 100).forEach(function (k: string) { delete _detailCache[k]; });
    }

    // Preserve selection across data reloads (e.g. panTo triggers moveend)
    if (_selected) {
        const selId = _featureId(_selected);
        let found: FeatureEntry | null = null;
        for (let i = 0; i < features.length; i++) {
            if (_featureId(features[i]) === selId) {
                found = features[i];
                break;
            }
        }
        if (found) {
            _selected = found;
            _buildTypeFilters();
            _applyFilters();
            _applyDim();
            return;
        }
        _restoreDim();
        _selected = null;
    }

    _buildTypeFilters();
    _applyFilters();
    if (!_isKiosk) showList();

    // Resolve pending selection from server search result click
    if (_pendingSelect && features.length > 0) {
        const pending = _pendingSelect;
        for (let i = 0; i < features.length; i++) {
            if (features[i].props.url === pending.url) {
                _pendingSelect = null;
                // Clear the search input so client filter doesn't hide the match
                const searchInput = document.getElementById('pw-search') as HTMLInputElement | null;
                if (searchInput) searchInput.value = '';
                _lastServerQuery = '';
                _clearServerResults();
                _applyFilters();
                selectFeature(features[i]);
                return;
            }
        }
    }

    // Resolve pending fly-to-select (from connected item click)
    if (_pendingFlySelectId && features.length > 0) {
        const id = _pendingFlySelectId;
        _pendingFlySelectId = '';
        for (let i = 0; i < features.length; i++) {
            if (_featureId(features[i]) === id) {
                selectFeature(features[i]);
                return;
            }
        }
    }
}

function showList(): void {
    if (_isKiosk) _kioskSidebarOpen();
    _setListBodyVisible(true);
    const detailPanel = document.getElementById('pw-panel-detail');
    if (detailPanel) detailPanel.style.display = 'none';
}

function showDetail(entry: FeatureEntry): void {
    if (_isKiosk) _kioskSidebarOpen();
    _setListBodyVisible(false);
    const detailPanel = document.getElementById('pw-panel-detail');
    if (detailPanel) detailPanel.style.display = '';

    // Set panel heading (e.g. "Structure Details")
    const heading = document.getElementById('pw-detail-heading');
    if (heading) {
        heading.textContent = _typeLabel(entry.featureType) + ' Details';
    }

    _renderDetail(entry);
}

function selectFeature(entry: FeatureEntry): void {
    _restoreDim();
    _selected = entry;
    _highlightListItem(entry);
    _highlightMapFeature(entry);
    showDetail(entry);
    if (_map && entry.latlng) {
        const zoom = _map.getZoom();
        // Zoom past disableClusteringAtZoom (18) for structures so the
        // individual marker is visible, not hidden inside a cluster.
        const minZoom = entry.featureType === 'structure' ? 18 : 16;
        if (zoom < minZoom) {
            _map.flyTo(entry.latlng, minZoom, { duration: 0.5 });
        } else {
            _map.panTo(entry.latlng);
        }
    }
    if (_onSelectionChange) _onSelectionChange();
}

function onFeatureCreated(entry: FeatureEntry): void {
    if (!_selected) return;
    if (_featureId(entry) === _featureId(_selected)) {
        _selected = entry;
        _reapplyHighlight(entry);
    }
}

// ---------------------------------------------------------------------------
// Dependency injection
// ---------------------------------------------------------------------------

export interface SidebarDeps {
    titleCase: (s: string) => string;
    esc: (s: string) => string;
    debounce: (fn: () => void, delay: number) => () => void;
    getCookie: (name: string) => string | null;
    structureColors: Record<string, string>;
    structureShapes: Record<string, string>;
    pathwayColors: Record<string, string>;
    apiBase: string;
}

function setDeps(deps: SidebarDeps): void {
    _titleCase = deps.titleCase;
    _esc = deps.esc;
    _debounce = deps.debounce;
    _getCookie = deps.getCookie;
    STRUCTURE_COLORS = deps.structureColors;
    STRUCTURE_SHAPES = deps.structureShapes;
    PATHWAY_COLORS = deps.pathwayColors;
    API_BASE = deps.apiBase;
}

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------

/** Return the ID string of the selected feature, or empty string. */
function getSelectedId(): string {
    return _selected ? _featureId(_selected) : '';
}

/** Select a feature by its ID string (e.g. "structure-123"). */
function selectById(id: string): boolean {
    if (!id) return false;
    for (let i = 0; i < _features.length; i++) {
        if (_featureId(_features[i]) === id) {
            selectFeature(_features[i]);
            return true;
        }
    }
    return false;
}

function onSelectionChange(cb: () => void): void {
    _onSelectionChange = cb;
}

export const Sidebar = {
    init,
    show,
    hide,
    setFeatures,
    showList,
    showDetail,
    selectFeature,
    selectById,
    getSelectedId,
    onFeatureCreated,
    onSelectionChange,
    setDeps,
    onServerSearch,
    setServerResults,
};

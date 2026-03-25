/**
 * Sidebar module for the full-page infrastructure map.
 *
 * Provides feature list, search/filter, detail panel with enriched
 * REST API data, inline name editing, and map feature highlighting.
 */

import type { FeatureEntry, FeatureType, DetailFieldDef, ResolvedValue } from './types/features';
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
        const latlngs = polyline.getLatLngs() as L.LatLng[];
        if (latlngs && _map) {
            _highlightOutline = L.polyline(latlngs, {
                color: _colorForFeature(entry),
                weight: 10,
                opacity: 0.35,
                interactive: false,
            }).addTo(_map);
        }
        polyline._origStyle = { weight: 3, opacity: 0.7 };
        polyline.setStyle({ weight: 5, opacity: 1 });
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
    if (countEl) countEl.textContent = String(_filtered.length);

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
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

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

    // Nested FK: {id, url, display, ...}
    if (typeof val === 'object' && val !== null) {
        const fk = val as { id?: number; url?: string; display?: string; name?: string };
        if (fk.display || fk.name || fk.id !== undefined) {
            return { text: fk.display || fk.name || String(fk.id), url: fk.url || null };
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
        _renderConnectedPathways(entry, container);
    }
}

function _renderConnectedPathways(entry: FeatureEntry, container: HTMLElement): void {
    const structId = entry.props.id;
    const connected = _features.filter(function (f: FeatureEntry) {
        if (f.featureType === 'structure') return false;
        const cached = _detailCache[_featureId(f)];
        if (!cached) return false;
        const startStruct = cached.start_structure as { id?: number } | number | null;
        const endStruct = cached.end_structure as { id?: number } | number | null;
        const startId = startStruct ? (typeof startStruct === 'object' ? startStruct.id : startStruct) : null;
        const endId = endStruct ? (typeof endStruct === 'object' ? endStruct.id : endStruct) : null;
        return startId === structId || endId === structId;
    });
    if (connected.length === 0) return;

    const sectionBody = _createSection(
        'Connected Pathways (' + connected.length + ')',
        container,
    );

    connected.forEach(function (f: FeatureEntry) {
        const item = document.createElement('div');
        item.className = 'pw-list-item';
        item.style.padding = '6px 0';

        const dot = document.createElement('span');
        dot.className = 'pw-list-dot';
        dot.style.background = _colorForFeature(f);
        item.appendChild(dot);

        const label = document.createElement('span');
        label.className = 'pw-list-label';
        label.textContent = f.props.name || 'Unnamed';
        item.appendChild(label);

        const typeBadge = document.createElement('span');
        typeBadge.className = 'pw-metric-badge pw-metric-muted';
        typeBadge.style.fontSize = '0.65em';
        typeBadge.style.padding = '1px 6px';
        typeBadge.textContent = _titleCase(_typeKeyForFeature(f));
        item.appendChild(typeBadge);

        item.addEventListener('click', function () {
            selectFeature(f);
        });

        sectionBody.appendChild(item);
    });
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

    // View in NetBox button
    if (p.url) {
        const link = document.createElement('a');
        link.href = p.url;
        link.className = 'btn btn-sm btn-primary w-100 mb-3';
        const icon = document.createElement('i');
        icon.className = 'mdi mdi-open-in-new';
        link.appendChild(icon);
        link.appendChild(document.createTextNode(' View in NetBox'));
        body.appendChild(link);
    }

    // Fetch enriched detail from REST API
    const detailContainer = document.createElement('div');
    body.appendChild(detailContainer);
    _fetchDetail(entry, detailContainer);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

function init(map: L.Map): void {
    _map = map;

    const closeBtn = document.getElementById('pw-sidebar-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', function () {
            hide();
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
            } else {
                hide();
            }
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
            _selected = null;
            _highlightListItem(null);
            const detailPanel = document.getElementById('pw-panel-detail');
            if (detailPanel && detailPanel.style.display !== 'none') {
                showList();
            }
        }
    });
}

function show(): void {
    const listPanel = document.getElementById('pw-panel-list');
    if (listPanel) listPanel.style.display = '';
}

function hide(): void {
    _unhighlightMapFeature();
    _selected = null;
    const listPanel = document.getElementById('pw-panel-list');
    const detailPanel = document.getElementById('pw-panel-detail');
    if (listPanel) listPanel.style.display = 'none';
    if (detailPanel) detailPanel.style.display = 'none';
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
            show();
            return;
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

function showList(): void {
    const listPanel = document.getElementById('pw-panel-list');
    const detailPanel = document.getElementById('pw-panel-detail');
    if (listPanel) listPanel.style.display = '';
    if (detailPanel) detailPanel.style.display = 'none';
}

function showDetail(entry: FeatureEntry): void {
    const listPanel = document.getElementById('pw-panel-list');
    const detailPanel = document.getElementById('pw-panel-detail');
    if (listPanel) listPanel.style.display = 'none';
    if (detailPanel) detailPanel.style.display = '';

    // Set panel heading (e.g. "Structure Details")
    const heading = document.getElementById('pw-detail-heading');
    if (heading) {
        heading.textContent = _typeLabel(entry.featureType) + ' Details';
    }

    _renderDetail(entry);
}

function selectFeature(entry: FeatureEntry): void {
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

export const Sidebar = {
    init,
    show,
    hide,
    setFeatures,
    showList,
    showDetail,
    selectFeature,
    onFeatureCreated,
    setDeps,
};

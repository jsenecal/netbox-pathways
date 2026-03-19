/**
 * Hover popover module for the full-page infrastructure map.
 *
 * Shows a lightweight tooltip with feature name and type on hover,
 * positioned near the cursor within the map container.
 */

import type { GeoJSONProperties } from './types/features';

// ---------------------------------------------------------------------------
// Module-level helpers injected via setDeps
// ---------------------------------------------------------------------------

let _titleCase: (s: string) => string;

// ---------------------------------------------------------------------------
// Internal state
// ---------------------------------------------------------------------------

let _el: HTMLDivElement | null = null;
let _map: L.Map | null = null;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function _position(latlng: L.LatLng): void {
    if (!_map || !_el) return;
    const pt = _map.latLngToContainerPoint(latlng);
    const cw = _map.getContainer().clientWidth;
    let x = pt.x + 14;
    let y = pt.y - 10;
    if (x + 200 > cw) x = pt.x - 200;
    if (y < 0) y = pt.y + 20;
    _el.style.left = x + 'px';
    _el.style.top = y + 'px';
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

function init(map: L.Map): void {
    _map = map;
    _el = document.createElement('div');
    _el.className = 'pw-popover';
    _el.style.display = 'none';
    map.getContainer().appendChild(_el);
}

function show(latlng: L.LatLng, props: GeoJSONProperties, popoverFields?: string[]): void {
    if (!_el) return;
    _el.textContent = '';

    // Name line
    const name = document.createElement('span');
    name.className = 'pw-popover-name';
    if (popoverFields && popoverFields.length > 0) {
        name.textContent = String(props[popoverFields[0]] ?? props.name ?? `#${props.id}`);
    } else {
        name.textContent = props.name || 'Unnamed';
    }
    _el.appendChild(name);

    // Type line
    let typeText = '';
    if (popoverFields && popoverFields.length > 1) {
        typeText = popoverFields.slice(1)
            .map(f => String(props[f] ?? ''))
            .filter(Boolean)
            .join(' / ');
    } else {
        const t = props.structure_type || props.pathway_type || '';
        typeText = t ? _titleCase(t) : '';
    }
    if (typeText) {
        const type = document.createElement('span');
        type.className = 'pw-popover-type';
        type.textContent = typeText;
        _el.appendChild(type);
    }

    _position(latlng);
    _el.style.display = '';
}

function hide(): void {
    if (_el) _el.style.display = 'none';
}

// ---------------------------------------------------------------------------
// Dependency injection
// ---------------------------------------------------------------------------

export interface PopoverDeps {
    titleCase: (s: string) => string;
}

function setDeps(deps: PopoverDeps): void {
    _titleCase = deps.titleCase;
}

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------

export const Popover = {
    init,
    show,
    hide,
    setDeps,
};

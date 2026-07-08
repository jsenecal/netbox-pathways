/**
 * Status visibility preferences for the full-page infrastructure map.
 *
 * Tracks which lifecycle statuses the user considers "inactive" and whether
 * inactive features are currently hidden. Both settings persist in
 * localStorage (same pattern as the route planner's pw_include_inactive).
 * The available status choices arrive from the /info endpoint, which also
 * carries each status's NetBox badge color.
 */

const HIDE_KEY = 'pw_hide_inactive';
const SET_KEY = 'pw_inactive_statuses';

export const DEFAULT_INACTIVE = ['retired', 'abandoned'];

export interface StatusChoice {
    value: string;
    label: string;
    color: string | null;
}

let _available: StatusChoice[] = [];

function setAvailableStatuses(statuses: StatusChoice[] | undefined): void {
    if (Array.isArray(statuses)) _available = statuses;
}

function getAvailableStatuses(): StatusChoice[] {
    return _available;
}

function colorFor(value: string): string | null {
    for (const s of _available) {
        if (s.value === value) return s.color;
    }
    return null;
}

function isHideInactive(): boolean {
    try {
        return localStorage.getItem(HIDE_KEY) === '1';
    } catch (_e) {
        return false;
    }
}

function setHideInactive(hide: boolean): void {
    try {
        localStorage.setItem(HIDE_KEY, hide ? '1' : '0');
    } catch (_e) { /* ignore */ }
}

function getInactiveSet(): string[] {
    try {
        const saved = localStorage.getItem(SET_KEY);
        if (saved) {
            const parsed = JSON.parse(saved) as unknown;
            if (Array.isArray(parsed)) return parsed.filter(v => typeof v === 'string');
        }
    } catch (_e) { /* fall through to default */ }
    return DEFAULT_INACTIVE.slice();
}

function setInactiveSet(values: string[]): void {
    try {
        localStorage.setItem(SET_KEY, JSON.stringify(values));
    } catch (_e) { /* ignore */ }
}

/**
 * Comma-joined ``exclude_status`` value for layer/info requests, or null
 * when hiding is off (or the inactive set is empty).
 */
function excludeParam(): string | null {
    if (!isHideInactive()) return null;
    const set = getInactiveSet();
    return set.length ? set.join(',') : null;
}

export const StatusPrefs = {
    setAvailableStatuses,
    getAvailableStatuses,
    colorFor,
    isHideInactive,
    setHideInactive,
    getInactiveSet,
    setInactiveSet,
    excludeParam,
};

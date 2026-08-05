/**
 * Occupancy visibility preference for the full-page infrastructure map.
 *
 * Tracks whether unoccupied features (pathways with no routed cable and
 * structures that terminate none) are currently hidden. Persists in
 * localStorage, same pattern as StatusPrefs' pw_hide_inactive.
 */

const HIDE_KEY = 'pw_hide_unoccupied';

function isHideUnoccupied(): boolean {
    try {
        return localStorage.getItem(HIDE_KEY) === '1';
    } catch (_e) {
        return false;
    }
}

function setHideUnoccupied(hide: boolean): void {
    try {
        localStorage.setItem(HIDE_KEY, hide ? '1' : '0');
    } catch (_e) { /* ignore */ }
}

/** ``occupied`` value for layer/info requests, or null when hiding is off. */
function occupiedParam(): string | null {
    return isHideUnoccupied() ? 'true' : null;
}

export const OccupancyPrefs = {
    isHideUnoccupied,
    setHideUnoccupied,
    occupiedParam,
};

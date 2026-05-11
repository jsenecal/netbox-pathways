/**
 * Wires the tab navigation and free-text Coordinates tab of the geometry
 * widget. The in-map helper buttons ("Use my location", "Paste coordinate")
 * live in widget-controls.ts as Leaflet controls and write directly to the
 * hidden input; this shell listens for those external commits via the
 * input's "change" event and resets the dirty-invalid flag accordingly.
 *
 * Hidden input remains the single source of truth. See issue #32.
 */

import { parseGeometryInput } from './coord-parser';

export interface WidgetShellHandles {
    fieldId: string;
    geomType: string;
    hiddenInput: HTMLInputElement;
    /** Replace the map's current geometry with the given GeoJSON. */
    loadGeometry: (geom: GeoJSON.Geometry | null) => void;
    /** Tell Leaflet to recompute size after the tab pane becomes visible. */
    invalidateMap: () => void;
}

function prettyGeoJson(text: string): string {
    if (!text.trim()) return '';
    try {
        return JSON.stringify(JSON.parse(text), null, 2);
    } catch {
        return text;
    }
}

function findWrapper(fieldId: string): HTMLElement | null {
    return document.querySelector<HTMLElement>(`.pathways-widget[data-field-id="${fieldId}"]`);
}

export function wireWidgetShell(handles: WidgetShellHandles): void {
    const wrapper = findWrapper(handles.fieldId);
    if (!wrapper) return;

    const mapTabBtn = wrapper.querySelector<HTMLElement>(`#${handles.fieldId}-tab-map-btn`);
    const coordTabBtn = wrapper.querySelector<HTMLElement>(`#${handles.fieldId}-tab-coords-btn`);
    const textarea = wrapper.querySelector<HTMLTextAreaElement>('[data-coord-textarea]');
    const coordError = wrapper.querySelector<HTMLElement>('[data-coord-error]');

    if (textarea) textarea.value = prettyGeoJson(handles.hiddenInput.value);

    // True when the last commit attempt failed: the textarea contains
    // unsaved invalid input that the user should see again on tab return.
    let coordCommitFailed = false;

    function showCoordError(msg: string): void {
        if (coordError) coordError.textContent = msg;
    }
    function clearCoordError(): void {
        if (coordError) coordError.textContent = '';
    }

    function commitTextarea(opts: { silent: boolean }): boolean {
        if (!textarea) return true;
        const result = parseGeometryInput(textarea.value, handles.geomType);
        if (result.error) {
            if (!opts.silent) showCoordError(result.error);
            return false;
        }
        clearCoordError();
        handles.hiddenInput.value = result.geometry ? JSON.stringify(result.geometry) : '';
        handles.hiddenInput.dispatchEvent(new Event('change', { bubbles: true }));
        handles.loadGeometry(result.geometry);
        return true;
    }

    if (mapTabBtn) {
        mapTabBtn.addEventListener('shown.bs.tab', () => {
            commitTextarea({ silent: true });
            handles.invalidateMap();
        });
    }
    if (coordTabBtn) {
        coordTabBtn.addEventListener('shown.bs.tab', () => {
            if (!textarea) return;
            if (coordCommitFailed) return;
            textarea.value = prettyGeoJson(handles.hiddenInput.value);
            clearCoordError();
        });
        coordTabBtn.addEventListener('hide.bs.tab', () => {
            coordCommitFailed = !commitTextarea({ silent: false });
        });
    }

    if (textarea) {
        textarea.addEventListener('blur', () => {
            coordCommitFailed = !commitTextarea({ silent: false });
        });
    }

    // Any external commit to the hidden input (map draw, helper buttons,
    // textarea success) clears the dirty-invalid flag so the next Coords
    // tab visit refreshes the textarea from the new hidden-input value.
    handles.hiddenInput.addEventListener('change', () => {
        coordCommitFailed = false;
    });
}

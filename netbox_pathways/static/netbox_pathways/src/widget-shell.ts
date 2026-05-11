/**
 * Wires the non-map parts of the geometry widget: tabs, free-text Coordinates
 * tab, "Use my location" button, and "Paste lat/lon..." inline form.
 *
 * Hidden input remains the single source of truth. The map writes to it via
 * pathways-field.ts; this shell reads from it (on tab show) and writes back
 * (on textarea commit, geolocation success, or paste-confirm).
 *
 * See netbox-pathways issue #32.
 */

import { parseGeometryInput } from './coord-parser';
import type { AppendResult } from './geom-ops';

export interface WidgetShellHandles {
    fieldId: string;
    geomType: string;
    hiddenInput: HTMLInputElement;
    /** Replace the map's current geometry with the given GeoJSON. */
    loadGeometry: (geom: GeoJSON.Geometry | null) => void;
    /** Apply one [lon, lat] point in LineString append mode (helper buttons). */
    appendLinePoint: (lon: number, lat: number) => AppendResult;
    /** Tell Leaflet to recompute size after the tab pane becomes visible. */
    invalidateMap: () => void;
}

function isLineMode(geomType: string): boolean {
    return geomType.replace(/\s+/g, '').toLowerCase() === 'linestring';
}

function prettyGeoJson(text: string): string {
    if (!text.trim()) return '';
    try {
        return JSON.stringify(JSON.parse(text), null, 2);
    } catch {
        return text;
    }
}

function setHidden(input: HTMLInputElement, geom: GeoJSON.Geometry | null): void {
    input.value = geom ? JSON.stringify(geom) : '';
    input.dispatchEvent(new Event('change', { bubbles: true }));
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
    const helperError = wrapper.querySelector<HTMLElement>('[data-helper-error]');
    const helperInfo = wrapper.querySelector<HTMLElement>('[data-helper-info]');
    const pasteForm = wrapper.querySelector<HTMLElement>('[data-paste-form]');
    const pasteToggleBtn = wrapper.querySelector<HTMLButtonElement>('[data-action="paste-toggle"]');
    const pasteConfirmBtn = wrapper.querySelector<HTMLButtonElement>('[data-action="paste-confirm"]');
    const pasteCancelBtn = wrapper.querySelector<HTMLButtonElement>('[data-action="paste-cancel"]');
    const geolocateBtn = wrapper.querySelector<HTMLButtonElement>('[data-action="geolocate"]');
    const pasteInput = wrapper.querySelector<HTMLInputElement>('[data-paste-input]');

    if (textarea) textarea.value = prettyGeoJson(handles.hiddenInput.value);

    // True when the last commit attempt failed: the textarea contains
    // unsaved invalid input that the user should see again on tab return.
    let coordCommitFailed = false;

    // ----- Tab events -----
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

    // ----- Textarea commit -----
    function commitTextarea(opts: { silent: boolean }): boolean {
        if (!textarea) return true;
        const value = textarea.value;
        const result = parseGeometryInput(value, handles.geomType);
        if (result.error) {
            if (!opts.silent) showCoordError(result.error);
            return false;
        }
        clearCoordError();
        setHidden(handles.hiddenInput, result.geometry);
        handles.loadGeometry(result.geometry);
        return true;
    }
    if (textarea) {
        textarea.addEventListener('blur', () => {
            coordCommitFailed = !commitTextarea({ silent: false });
        });
    }

    function showCoordError(msg: string): void {
        if (coordError) coordError.textContent = msg;
    }
    function clearCoordError(): void {
        if (coordError) coordError.textContent = '';
    }
    function showHelperError(msg: string): void {
        if (helperError) helperError.textContent = msg;
        if (msg) {
            window.setTimeout(() => {
                if (helperError && helperError.textContent === msg) helperError.textContent = '';
            }, 6000);
        }
    }
    function clearHelperError(): void {
        if (helperError) helperError.textContent = '';
    }
    function showHelperInfo(msg: string): void {
        if (helperInfo) helperInfo.textContent = msg;
    }
    function clearHelperInfo(): void {
        if (helperInfo) helperInfo.textContent = '';
    }

    // ----- Paste lat/lon form (in-place swap with the toggle button) -----
    function openPasteForm(): void {
        if (!pasteForm || !pasteToggleBtn) return;
        pasteToggleBtn.classList.add('d-none');
        pasteForm.classList.remove('d-none');
        pasteForm.classList.add('d-flex');
        pasteToggleBtn.setAttribute('aria-expanded', 'true');
        if (pasteInput) {
            pasteInput.value = '';
            pasteInput.focus();
        }
    }
    function closePasteForm(): void {
        if (!pasteForm || !pasteToggleBtn) return;
        pasteForm.classList.add('d-none');
        pasteForm.classList.remove('d-flex');
        pasteToggleBtn.classList.remove('d-none');
        pasteToggleBtn.setAttribute('aria-expanded', 'false');
        if (pasteInput) pasteInput.value = '';
        clearHelperError();
        pasteToggleBtn.focus();
    }
    function confirmPaste(): void {
        const raw = pasteInput?.value.trim() ?? '';
        if (!raw) {
            showHelperError('Enter a coordinate.');
            return;
        }
        const result = parseGeometryInput(raw, 'Point');
        if (result.error || !result.geometry || result.geometry.type !== 'Point') {
            showHelperError(result.error || 'Could not parse coordinate.');
            return;
        }
        const [lon, lat] = (result.geometry as GeoJSON.Point).coordinates;
        applyPoint(lon, lat);
        closePasteForm();
    }
    if (pasteToggleBtn) {
        pasteToggleBtn.addEventListener('click', openPasteForm);
    }
    if (pasteConfirmBtn) pasteConfirmBtn.addEventListener('click', confirmPaste);
    if (pasteCancelBtn) pasteCancelBtn.addEventListener('click', closePasteForm);
    if (pasteInput) {
        pasteInput.addEventListener('keydown', (e: KeyboardEvent) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                confirmPaste();
            } else if (e.key === 'Escape') {
                e.preventDefault();
                closePasteForm();
            }
        });
    }

    // ----- Geolocation -----
    if (geolocateBtn) {
        geolocateBtn.addEventListener('click', () => {
            if (!navigator.geolocation) {
                showHelperError('Geolocation is not supported by this browser.');
                return;
            }
            if (!window.isSecureContext) {
                showHelperError('Geolocation requires HTTPS.');
                return;
            }
            geolocateBtn.disabled = true;
            clearHelperError();
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    geolocateBtn.disabled = false;
                    applyPoint(pos.coords.longitude, pos.coords.latitude);
                },
                (err) => {
                    geolocateBtn.disabled = false;
                    const message = err.code === err.PERMISSION_DENIED
                        ? 'Location permission denied.'
                        : err.code === err.POSITION_UNAVAILABLE
                            ? 'Location unavailable.'
                            : err.code === err.TIMEOUT
                                ? 'Location request timed out.'
                                : 'Could not get location.';
                    showHelperError(message);
                },
                { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
            );
        });
    }

    // ----- Apply a single point (called by paste-confirm and geolocate) -----
    function applyPoint(lon: number, lat: number): void {
        clearHelperInfo();
        // An explicit helper action supersedes any unsaved textarea input.
        coordCommitFailed = false;
        if (isLineMode(handles.geomType)) {
            const result = handles.appendLinePoint(lon, lat);
            if (result.kind === 'pending') {
                showHelperInfo('Vertex 1 of 2 saved -- add one more to form a line.');
                return;
            }
            setHidden(handles.hiddenInput, result.geometry);
            return;
        }
        const point: GeoJSON.Point = { type: 'Point', coordinates: [lon, lat] };
        setHidden(handles.hiddenInput, point);
        handles.loadGeometry(point);
    }
}

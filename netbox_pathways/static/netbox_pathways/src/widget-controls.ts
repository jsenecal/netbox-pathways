/**
 * In-map Leaflet controls for the geometry widget: "Use my current location"
 * and "Paste coordinate". Both emit a single [lon, lat] point via the
 * `onPoint` callback; the consumer decides whether to set or append.
 *
 * Rendered as a single `leaflet-bar` with two stacked buttons, sitting in
 * the top-left corner between the default zoom control and geoman's draw
 * toolbar. The paste button expands a small inline form to the right of
 * the bar. See issue #32.
 */

import { parseGeometryInput } from './coord-parser';

export interface PointHelperOptions {
    onPoint: (lon: number, lat: number) => void;
    /** Optional callback for transient status / error messages. */
    showInfo?: (msg: string) => void;
}

export function addPointHelperControl(map: L.Map, opts: PointHelperOptions): L.Control {
    const HelperControl = L.Control.extend({
        options: { position: 'topleft' as L.ControlPosition },

        onAdd(this: L.Control): HTMLElement {
            const wrapper = L.DomUtil.create('div', 'pathways-helpers-wrapper');

            const bar = L.DomUtil.create('div', 'leaflet-bar pathways-helpers', wrapper);

            const geoBtn = L.DomUtil.create('a', 'pathways-helper-btn', bar) as HTMLAnchorElement;
            geoBtn.href = '#';
            geoBtn.title = 'Use my current location';
            geoBtn.setAttribute('role', 'button');
            geoBtn.setAttribute('aria-label', 'Use my current location');
            L.DomUtil.create('i', 'mdi mdi-crosshairs-gps', geoBtn);

            const pasteBtn = L.DomUtil.create('a', 'pathways-helper-btn', bar) as HTMLAnchorElement;
            pasteBtn.href = '#';
            pasteBtn.title = 'Paste coordinate';
            pasteBtn.setAttribute('role', 'button');
            pasteBtn.setAttribute('aria-expanded', 'false');
            pasteBtn.setAttribute('aria-label', 'Paste coordinate');
            L.DomUtil.create('i', 'mdi mdi-content-paste', pasteBtn);

            const panel = L.DomUtil.create('div', 'pathways-paste-panel d-none', wrapper);
            const input = L.DomUtil.create('input', 'pathways-paste-input', panel) as HTMLInputElement;
            input.type = 'text';
            input.placeholder = '45.5017, -73.5673';
            input.autocomplete = 'off';
            input.setAttribute('aria-label', 'Lat, lon');
            const confirmBtn = L.DomUtil.create('a', 'pathways-helper-btn pathways-paste-confirm', panel) as HTMLAnchorElement;
            confirmBtn.href = '#';
            confirmBtn.title = 'Add';
            confirmBtn.setAttribute('role', 'button');
            confirmBtn.setAttribute('aria-label', 'Add coordinate');
            L.DomUtil.create('i', 'mdi mdi-check', confirmBtn);
            const cancelBtn = L.DomUtil.create('a', 'pathways-helper-btn pathways-paste-cancel', panel) as HTMLAnchorElement;
            cancelBtn.href = '#';
            cancelBtn.title = 'Cancel';
            cancelBtn.setAttribute('role', 'button');
            cancelBtn.setAttribute('aria-label', 'Cancel');
            L.DomUtil.create('i', 'mdi mdi-close', cancelBtn);

            const status = L.DomUtil.create('div', 'pathways-helper-status d-none', wrapper);
            status.setAttribute('role', 'status');
            status.setAttribute('aria-live', 'polite');

            L.DomEvent.disableClickPropagation(wrapper);
            L.DomEvent.disableScrollPropagation(wrapper);

            let statusTimer: number | null = null;
            function showStatus(msg: string, isError: boolean): void {
                status.textContent = msg;
                status.classList.toggle('is-error', isError);
                status.classList.remove('d-none');
                if (statusTimer !== null) window.clearTimeout(statusTimer);
                statusTimer = window.setTimeout(() => {
                    status.classList.add('d-none');
                    status.textContent = '';
                    statusTimer = null;
                }, 6000);
            }
            function clearStatus(): void {
                if (statusTimer !== null) window.clearTimeout(statusTimer);
                status.classList.add('d-none');
                status.textContent = '';
                statusTimer = null;
            }
            // Outside code can pipe info messages through the same status strip.
            opts.showInfo = (msg: string) => showStatus(msg, false);

            function openPaste(): void {
                panel.classList.remove('d-none');
                panel.classList.add('d-flex');
                pasteBtn.setAttribute('aria-expanded', 'true');
                pasteBtn.classList.add('is-active');
                input.value = '';
                input.focus();
                clearStatus();
            }
            function closePaste(): void {
                panel.classList.add('d-none');
                panel.classList.remove('d-flex');
                pasteBtn.setAttribute('aria-expanded', 'false');
                pasteBtn.classList.remove('is-active');
                input.value = '';
            }
            function confirmPaste(): void {
                const raw = input.value.trim();
                if (!raw) {
                    showStatus('Enter a coordinate.', true);
                    return;
                }
                const result = parseGeometryInput(raw, 'Point');
                if (result.error || !result.geometry || result.geometry.type !== 'Point') {
                    showStatus(result.error || 'Could not parse coordinate.', true);
                    return;
                }
                const [lon, lat] = (result.geometry as GeoJSON.Point).coordinates;
                opts.onPoint(lon, lat);
                closePaste();
            }

            L.DomEvent.on(geoBtn, 'click', (e: Event) => {
                L.DomEvent.preventDefault(e);
                if (!navigator.geolocation) {
                    showStatus('Geolocation is not supported by this browser.', true);
                    return;
                }
                if (!window.isSecureContext) {
                    showStatus('Geolocation requires HTTPS.', true);
                    return;
                }
                geoBtn.classList.add('is-busy');
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        geoBtn.classList.remove('is-busy');
                        opts.onPoint(pos.coords.longitude, pos.coords.latitude);
                    },
                    (err) => {
                        geoBtn.classList.remove('is-busy');
                        const msg = err.code === err.PERMISSION_DENIED
                            ? 'Location permission denied.'
                            : err.code === err.POSITION_UNAVAILABLE
                                ? 'Location unavailable.'
                                : err.code === err.TIMEOUT
                                    ? 'Location request timed out.'
                                    : 'Could not get location.';
                        showStatus(msg, true);
                    },
                    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
                );
            });

            L.DomEvent.on(pasteBtn, 'click', (e: Event) => {
                L.DomEvent.preventDefault(e);
                if (panel.classList.contains('d-none')) openPaste();
                else closePaste();
            });
            L.DomEvent.on(confirmBtn, 'click', (e: Event) => {
                L.DomEvent.preventDefault(e);
                confirmPaste();
            });
            L.DomEvent.on(cancelBtn, 'click', (e: Event) => {
                L.DomEvent.preventDefault(e);
                closePaste();
            });
            input.addEventListener('keydown', (e: KeyboardEvent) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    confirmPaste();
                } else if (e.key === 'Escape') {
                    e.preventDefault();
                    closePaste();
                }
            });

            return wrapper;
        },
    });
    const instance = new HelperControl();
    instance.addTo(map);
    return instance;
}

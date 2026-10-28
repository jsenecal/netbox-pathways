/**
 * Tests for the map widget field module.
 *
 * Focus: the widget's minimum zoom floor -- editing a single geometry never
 * needs a world-level view, so the widget clamps zoom-out independently of
 * the full-page map's minZoom.
 */

import { describe, it, expect, afterEach } from 'vitest';
import { resolveWidgetMinZoom, WIDGET_MIN_ZOOM } from './pathways-field';

describe('resolveWidgetMinZoom', () => {
    it('defaults to the widget floor, not the full-page map minimum', () => {
        expect(WIDGET_MIN_ZOOM).toBe(14);
        expect(resolveWidgetMinZoom({})).toBe(14);
    });

    it('ignores the full-page minZoom (always 1 in server config)', () => {
        expect(resolveWidgetMinZoom({ minZoom: 1 })).toBe(14);
    });

    it('honors an explicit widgetMinZoom override', () => {
        expect(resolveWidgetMinZoom({ widgetMinZoom: 3 })).toBe(3);
        expect(resolveWidgetMinZoom({ widgetMinZoom: 12 })).toBe(12);
    });
});

/**
 * A stand-in for Leaflet: every property is another stand-in and every call
 * or `new` returns one, so initWidget runs end to end without a real map.
 */
function leafletStub(): any {
    const stub: any = new Proxy(function () {}, {
        get: (_target, prop) => (prop === Symbol.toPrimitive ? () => '' : stub),
        apply: () => stub,
        construct: () => stub,
    });
    return stub;
}

describe('widget initialisation after an htmx swap', () => {
    afterEach(() => {
        document.body.innerHTML = '';
        delete (globalThis as any).L;
    });

    function insertWidget(fieldId: string): HTMLElement {
        const wrapper = document.createElement('div');
        wrapper.innerHTML = `
            <div class="pathways-map-widget" data-field-id="${fieldId}" data-geom-type="LineString"></div>
            <input type="hidden" id="${fieldId}" value="">`;
        document.body.appendChild(wrapper);
        return wrapper.querySelector<HTMLElement>('.pathways-map-widget')!;
    }

    it('initialises a widget swapped in after page load, once', () => {
        const mapContainers: HTMLElement[] = [];
        const L = leafletStub();
        (globalThis as any).L = new Proxy(L, {
            get: (target, prop) =>
                prop === 'map'
                    ? (container: HTMLElement) => { mapContainers.push(container); return L; }
                    : target[prop],
        });
        const widget = insertWidget('id_geometry');

        document.body.dispatchEvent(new Event('htmx:afterSettle', { bubbles: true }));
        document.body.dispatchEvent(new Event('htmx:afterSettle', { bubbles: true }));

        expect(mapContainers).toEqual([widget]);
    });
});

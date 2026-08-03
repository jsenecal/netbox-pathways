/**
 * Tests for the geometry widget's in-map controls.
 *
 * Covers the maximize toggle: the class it drives, the icon it swaps, the
 * resize it triggers so Leaflet re-measures, and the Escape handling that
 * has to stay out of the paste panel's way.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { addMaximizeControl, MAXIMIZED_CLASS } from './widget-controls';

// ---------------------------------------------------------------------------
// Stub Leaflet globals. addTo() runs onAdd() the way Leaflet does, so the
// control's onReady wiring happens during setup.
// ---------------------------------------------------------------------------

(globalThis as any).L = {
    Control: {
        extend: (proto: any) =>
            class {
                options = proto.options;
                onAdd = proto.onAdd;
                _container: HTMLElement | undefined;
                addTo(map: any) {
                    this._container = this.onAdd(map);
                    return this;
                }
                getContainer() {
                    return this._container;
                }
            },
    },
    DomUtil: {
        create: (tag: string, className?: string, parent?: HTMLElement) => {
            const el = document.createElement(tag);
            if (className) el.className = className;
            if (parent) parent.appendChild(el);
            return el;
        },
    },
    DomEvent: {
        on: (el: HTMLElement, type: string, fn: EventListener) => el.addEventListener(type, fn),
        preventDefault: (e: Event) => e.preventDefault(),
        disableClickPropagation: vi.fn(),
    },
};

describe('addMaximizeControl', () => {
    let target: HTMLElement;
    let onResize: ReturnType<typeof vi.fn>;
    let button: HTMLAnchorElement;

    beforeEach(() => {
        document.body.innerHTML = '';
        target = document.createElement('div');
        target.className = 'pathways-map-widget';
        document.body.appendChild(target);
        onResize = vi.fn();

        const control = addMaximizeControl({} as L.Map, { target, onResize });
        // The container is not in the document -- Leaflet would place it in
        // the map pane -- so reach it through the control.
        button = control.getContainer()!.querySelector('a')!;
    });

    function pressEscape(on: EventTarget = document, cancelled = false): KeyboardEvent {
        const event = new KeyboardEvent('keydown', {
            key: 'Escape',
            bubbles: true,
            cancelable: true,
        });
        if (cancelled) event.preventDefault();
        on.dispatchEvent(event);
        return event;
    }

    it('toggles the shared maximized class on the map element', () => {
        expect(target.classList.contains(MAXIMIZED_CLASS)).toBe(false);

        button.click();
        expect(target.classList.contains(MAXIMIZED_CLASS)).toBe(true);

        button.click();
        expect(target.classList.contains(MAXIMIZED_CLASS)).toBe(false);
    });

    it('swaps the icon and title to match the current state', () => {
        const icon = button.querySelector('i')!;
        expect(icon.className).toContain('mdi-fullscreen');
        expect(button.title).toBe('Full screen');

        button.click();
        expect(icon.className).toContain('mdi-fullscreen-exit');
        expect(button.title).toBe('Exit full screen');

        button.click();
        expect(icon.className).toContain('mdi-fullscreen');
        expect(icon.className).not.toContain('mdi-fullscreen-exit');
    });

    it('holds the page still and drops the scrollbar gutter while maximized', () => {
        // NetBox reserves a gutter with scrollbar-gutter: stable, and a fixed
        // overlay cannot cover it -- see setPageLocked.
        const root = document.documentElement;

        button.click();
        expect(root.style.overflow).toBe('hidden');
        expect(root.style.scrollbarGutter).toBe('auto');

        button.click();
        expect(root.style.overflow).toBe('');
        expect(root.style.scrollbarGutter).toBe('');
    });

    it('asks the map to re-measure on the way in and on the way out', () => {
        button.click();
        expect(onResize).toHaveBeenCalledTimes(1);

        button.click();
        expect(onResize).toHaveBeenCalledTimes(2);
    });

    it('leaves full screen on Escape', () => {
        button.click();

        const event = pressEscape();

        expect(target.classList.contains(MAXIMIZED_CLASS)).toBe(false);
        expect(event.defaultPrevented).toBe(true);
    });

    it('ignores Escape that something nearer already handled', () => {
        // The paste panel calls preventDefault() on its own Escape, and it
        // sits inside the map -- closing it must not also unmaximize.
        button.click();

        pressEscape(document, true);

        expect(target.classList.contains(MAXIMIZED_CLASS)).toBe(true);
    });

    it('does not consume Escape when the map is not maximized', () => {
        const event = pressEscape();

        expect(event.defaultPrevented).toBe(false);
        expect(onResize).not.toHaveBeenCalled();
    });

    it('goes inert once the map leaves the page', () => {
        // The keydown handler is bound to the document and never unbound, so
        // a torn-down widget must not keep answering for the live one.
        button.click();
        target.remove();

        const event = pressEscape();

        expect(event.defaultPrevented).toBe(false);
        expect(target.classList.contains(MAXIMIZED_CLASS)).toBe(true);
    });
});

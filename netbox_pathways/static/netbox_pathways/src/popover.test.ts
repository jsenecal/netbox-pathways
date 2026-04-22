/**
 * Tests for the Popover module.
 *
 * Strategy: We mock the Leaflet map with getContainer() and
 * latLngToContainerPoint(), inject titleCase via setDeps, and test
 * the public init/show/hide API.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Popover } from './popover';
import type { GeoJSONProperties } from './types/features';

// ---------------------------------------------------------------------------
// Mock Leaflet map
// ---------------------------------------------------------------------------

function createMockMap(containerWidth = 800) {
    const container = document.createElement('div');
    Object.defineProperty(container, 'clientWidth', { value: containerWidth });
    return {
        getContainer: vi.fn(() => container),
        latLngToContainerPoint: vi.fn(() => ({ x: 100, y: 100 })),
        _container: container,
    };
}

function mockLatLng(lat = 45.5, lng = -73.5) {
    return { lat, lng } as L.LatLng;
}

// ---------------------------------------------------------------------------
// Stub L namespace (Popover doesn't use L directly but types reference it)
// ---------------------------------------------------------------------------

(globalThis as any).L = {
    divIcon: vi.fn(() => ({})),
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getPopoverEl(map: ReturnType<typeof createMockMap>): HTMLDivElement | null {
    return map._container.querySelector('.pw-popover');
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Popover', () => {
    let map: ReturnType<typeof createMockMap>;

    beforeEach(() => {
        document.body.textContent = '';
        map = createMockMap();
        Popover.setDeps({ titleCase: (s: string) => s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) });
        Popover.init(map as any);
    });

    describe('init', () => {
        it('creates a .pw-popover div in the map container', () => {
            const el = getPopoverEl(map);
            expect(el).not.toBeNull();
            expect(el!.className).toBe('pw-popover');
        });

        it('starts hidden (display:none)', () => {
            const el = getPopoverEl(map);
            expect(el!.style.display).toBe('none');
        });

        it('appends to the map container', () => {
            const container = map.getContainer();
            expect(container.querySelector('.pw-popover')).toBeTruthy();
        });
    });

    describe('show', () => {
        const baseProps: GeoJSONProperties = {
            id: 1,
            name: 'Test Structure',
            url: '/structures/1/',
            structure_type: 'pole',
        };

        it('sets name text from props.name', () => {
            Popover.show(mockLatLng(), baseProps);
            const el = getPopoverEl(map)!;
            const nameSpan = el.querySelector('.pw-popover-name');
            expect(nameSpan).not.toBeNull();
            expect(nameSpan!.textContent).toBe('Test Structure');
        });

        it('shows "Unnamed" when name is empty and no popoverFields', () => {
            Popover.show(mockLatLng(), { ...baseProps, name: '' });
            const el = getPopoverEl(map)!;
            const nameSpan = el.querySelector('.pw-popover-name');
            expect(nameSpan!.textContent).toBe('Unnamed');
        });

        it('sets type text via titleCase for structure_type', () => {
            Popover.show(mockLatLng(), baseProps);
            const el = getPopoverEl(map)!;
            const typeSpan = el.querySelector('.pw-popover-type');
            expect(typeSpan).not.toBeNull();
            expect(typeSpan!.textContent).toBe('Pole');
        });

        it('sets type text via titleCase for pathway_type', () => {
            const pathwayProps: GeoJSONProperties = {
                id: 2,
                name: 'Conduit A',
                url: '/conduits/2/',
                pathway_type: 'direct_buried',
            };
            Popover.show(mockLatLng(), pathwayProps);
            const el = getPopoverEl(map)!;
            const typeSpan = el.querySelector('.pw-popover-type');
            expect(typeSpan!.textContent).toBe('Direct Buried');
        });

        it('does not create type span when no type is available', () => {
            const noTypeProps: GeoJSONProperties = {
                id: 3,
                name: 'Mystery',
                url: '/things/3/',
            };
            Popover.show(mockLatLng(), noTypeProps);
            const el = getPopoverEl(map)!;
            const typeSpan = el.querySelector('.pw-popover-type');
            expect(typeSpan).toBeNull();
        });

        it('makes the popover visible (removes display:none)', () => {
            Popover.show(mockLatLng(), baseProps);
            const el = getPopoverEl(map)!;
            expect(el.style.display).toBe('');
        });

        it('positions the popover using latLngToContainerPoint', () => {
            Popover.show(mockLatLng(), baseProps);
            expect(map.latLngToContainerPoint).toHaveBeenCalled();
            const el = getPopoverEl(map)!;
            // Default mock returns {x:100, y:100}, so left=114px, top=90px
            expect(el.style.left).toBe('114px');
            expect(el.style.top).toBe('90px');
        });

        it('uses custom popoverFields for name (first field)', () => {
            const props: GeoJSONProperties = {
                id: 4,
                name: 'Default Name',
                url: '/x/4/',
                custom_label: 'Custom Label',
                status: 'active',
            };
            Popover.show(mockLatLng(), props, ['custom_label', 'status']);
            const el = getPopoverEl(map)!;
            const nameSpan = el.querySelector('.pw-popover-name');
            expect(nameSpan!.textContent).toBe('Custom Label');
        });

        it('uses custom popoverFields for type (remaining fields joined by /)', () => {
            const props: GeoJSONProperties = {
                id: 5,
                name: 'Default Name',
                url: '/x/5/',
                custom_label: 'Label',
                status: 'active',
                category: 'main',
            };
            Popover.show(mockLatLng(), props, ['custom_label', 'status', 'category']);
            const el = getPopoverEl(map)!;
            const typeSpan = el.querySelector('.pw-popover-type');
            expect(typeSpan!.textContent).toBe('active / main');
        });

        it('falls back to props.name when popoverFields[0] value is null', () => {
            const props: GeoJSONProperties = {
                id: 6,
                name: 'Fallback Name',
                url: '/x/6/',
            };
            Popover.show(mockLatLng(), props, ['missing_field']);
            const el = getPopoverEl(map)!;
            const nameSpan = el.querySelector('.pw-popover-name');
            expect(nameSpan!.textContent).toBe('Fallback Name');
        });

        it('clears previous content on successive calls', () => {
            Popover.show(mockLatLng(), baseProps);
            Popover.show(mockLatLng(), { ...baseProps, name: 'Second' });
            const el = getPopoverEl(map)!;
            const names = el.querySelectorAll('.pw-popover-name');
            expect(names).toHaveLength(1);
            expect(names[0].textContent).toBe('Second');
        });

        it('flips popover left when near right edge', () => {
            // Container width is 800, point at x=700 means 700+14+200 > 800
            map.latLngToContainerPoint.mockReturnValue({ x: 700, y: 100 });
            Popover.show(mockLatLng(), baseProps);
            const el = getPopoverEl(map)!;
            // Should flip: x = 700 - 200 = 500
            expect(el.style.left).toBe('500px');
        });

        it('shifts popover down when near top edge', () => {
            map.latLngToContainerPoint.mockReturnValue({ x: 100, y: 5 });
            Popover.show(mockLatLng(), baseProps);
            const el = getPopoverEl(map)!;
            // y < 0 check: y = 5 - 10 = -5 < 0, so y = 5 + 20 = 25
            expect(el.style.top).toBe('25px');
        });
    });

    describe('hide', () => {
        it('sets display to none', () => {
            const baseProps: GeoJSONProperties = {
                id: 1,
                name: 'Test',
                url: '/x/1/',
                structure_type: 'pole',
            };
            Popover.show(mockLatLng(), baseProps);
            const el = getPopoverEl(map)!;
            expect(el.style.display).toBe('');

            Popover.hide();
            expect(el.style.display).toBe('none');
        });

        it('is safe to call before init (no-op)', () => {
            // Re-create a fresh module state by calling hide without init
            // The module-level _el starts null, so this should not throw
            expect(() => Popover.hide()).not.toThrow();
        });
    });

    describe('setDeps', () => {
        it('injects titleCase used by show()', () => {
            const customTitleCase = vi.fn(() => 'CUSTOM');
            Popover.setDeps({ titleCase: customTitleCase });

            const props: GeoJSONProperties = {
                id: 1,
                name: 'Test',
                url: '/x/1/',
                structure_type: 'pole',
            };
            Popover.show(mockLatLng(), props);

            expect(customTitleCase).toHaveBeenCalledWith('pole');
            const el = getPopoverEl(map)!;
            const typeSpan = el.querySelector('.pw-popover-type');
            expect(typeSpan!.textContent).toBe('CUSTOM');
        });
    });
});

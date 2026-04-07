/**
 * Tests for the Sidebar module.
 *
 * Strategy: We import the real Sidebar module, set up minimal DOM fixtures
 * and a stub Leaflet map, then test the public API. Each test group
 * re-initialises the sidebar to avoid state leaking between tests.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Sidebar } from './sidebar';
import type { FeatureEntry } from './types/features';

// ---------------------------------------------------------------------------
// Stub Leaflet globals (sidebar.ts references L.* at runtime)
// ---------------------------------------------------------------------------

const mapListeners: Record<string, Function[]> = {};

function createMockMap() {
    mapListeners['click'] = [];
    return {
        on(event: string, fn: Function) {
            if (!mapListeners[event]) mapListeners[event] = [];
            mapListeners[event].push(fn);
        },
        off: vi.fn(),
        panTo: vi.fn(),
        flyTo: vi.fn(),
        getZoom: vi.fn(() => 14),
    };
}

// Minimal L namespace for type compatibility
(globalThis as any).L = {
    divIcon: vi.fn(() => ({})),
    polyline: vi.fn(() => ({ addTo: vi.fn(), remove: vi.fn() })),
};

// ---------------------------------------------------------------------------
// DOM fixture — builds the required elements programmatically
// ---------------------------------------------------------------------------

function buildDOM(kiosk = false) {
    document.body.textContent = '';

    const sb = document.createElement('div');
    sb.id = 'pw-sidebar';
    document.body.appendChild(sb);

    const toggleBtn = document.createElement('button');
    toggleBtn.id = 'pw-sidebar-toggle';
    sb.appendChild(toggleBtn);

    const chevron = document.createElement('i');
    chevron.id = 'pw-sidebar-chevron';
    sb.appendChild(chevron);

    const listBody = document.createElement('div');
    listBody.id = 'pw-panel-list-body';
    sb.appendChild(listBody);

    const search = document.createElement('input');
    search.id = 'pw-search';
    search.type = 'text';
    listBody.appendChild(search);

    const filters = document.createElement('div');
    filters.id = 'pw-type-filters';
    listBody.appendChild(filters);

    const featureList = document.createElement('div');
    featureList.id = 'pw-feature-list';
    listBody.appendChild(featureList);

    const count = document.createElement('span');
    count.id = 'pw-list-count';
    listBody.appendChild(count);

    const detailPanel = document.createElement('div');
    detailPanel.id = 'pw-panel-detail';
    detailPanel.style.display = 'none';
    sb.appendChild(detailPanel);

    const backBtn = document.createElement('button');
    backBtn.id = 'pw-detail-back';
    detailPanel.appendChild(backBtn);

    const heading = document.createElement('div');
    heading.id = 'pw-detail-heading';
    detailPanel.appendChild(heading);

    const detailBody = document.createElement('div');
    detailBody.id = 'pw-detail-body';
    detailPanel.appendChild(detailBody);

    if (kiosk) {
        const closeBtn = document.createElement('button');
        closeBtn.id = 'pw-kiosk-close';
        sb.appendChild(closeBtn);
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockDeps() {
    Sidebar.setDeps({
        titleCase: (s: string) => s.charAt(0).toUpperCase() + s.slice(1),
        esc: (s: string) => s,
        debounce: (fn: () => void) => fn,
        getCookie: () => null,
        structureColors: { pole: '#8B4513', manhole: '#616161' },
        structureShapes: {},
        pathwayColors: { conduit: '#1565C0' },
        apiBase: '/api/plugins/pathways/geo/',
    });
}

function makeMockLayer() {
    return {
        getIcon: vi.fn(() => ({})),
        setIcon: vi.fn(),
        getLatLngs: vi.fn(() => []),
        setStyle: vi.fn(),
    };
}

function makeEntry(overrides: Partial<FeatureEntry> = {}): FeatureEntry {
    return {
        props: { id: 1, name: 'Test Feature', url: '/structures/1/', structure_type: 'pole' },
        featureType: 'structure',
        layer: makeMockLayer() as any,
        latlng: { lat: 45.5, lng: -73.5 } as any,
        ...overrides,
    };
}

function sidebar() { return document.getElementById('pw-sidebar')!; }
function listBodyEl() { return document.getElementById('pw-panel-list-body')!; }
function detailPanelEl() { return document.getElementById('pw-panel-detail')!; }
function countEl() { return document.getElementById('pw-list-count')!; }

// ---------------------------------------------------------------------------
// Tests — Normal mode
// ---------------------------------------------------------------------------

describe('Sidebar (normal mode)', () => {
    let map: ReturnType<typeof createMockMap>;

    beforeEach(() => {
        buildDOM(false);
        mockDeps();
        map = createMockMap();
        Sidebar.init(map as any, false);
    });

    describe('show / hide', () => {
        it('show() removes pw-sidebar-hidden class', () => {
            sidebar().classList.add('pw-sidebar-hidden');
            Sidebar.show();
            expect(sidebar().classList.contains('pw-sidebar-hidden')).toBe(false);
        });

        it('hide() adds pw-sidebar-hidden class', () => {
            Sidebar.hide();
            expect(sidebar().classList.contains('pw-sidebar-hidden')).toBe(true);
        });

        it('show() expands list body', () => {
            listBodyEl().classList.add('collapsed');
            Sidebar.show();
            expect(listBodyEl().classList.contains('collapsed')).toBe(false);
        });
    });

    describe('showList / showDetail', () => {
        it('showList() shows list body and hides detail panel', () => {
            detailPanelEl().style.display = '';
            listBodyEl().classList.add('collapsed');
            Sidebar.showList();
            expect(listBodyEl().classList.contains('collapsed')).toBe(false);
            expect(detailPanelEl().style.display).toBe('none');
        });

        it('showDetail() hides list body and shows detail panel', () => {
            const entry = makeEntry();
            Sidebar.showDetail(entry);
            expect(listBodyEl().classList.contains('collapsed')).toBe(true);
            expect(detailPanelEl().style.display).toBe('');
        });

        it('showDetail() sets heading text', () => {
            const entry = makeEntry();
            Sidebar.showDetail(entry);
            const heading = document.getElementById('pw-detail-heading')!;
            expect(heading.textContent).toBe('Structure Details');
        });
    });

    describe('list body collapse toggle', () => {
        it('toggle button collapses expanded list body', () => {
            // List body starts expanded (no collapsed class)
            const toggleBtn = document.getElementById('pw-sidebar-toggle')!;
            toggleBtn.click();
            expect(listBodyEl().classList.contains('collapsed')).toBe(true);
        });

        it('toggle button expands collapsed list body', () => {
            listBodyEl().classList.add('collapsed');
            const toggleBtn = document.getElementById('pw-sidebar-toggle')!;
            toggleBtn.click();
            expect(listBodyEl().classList.contains('collapsed')).toBe(false);
        });

        it('toggle does NOT affect sidebar visibility', () => {
            const toggleBtn = document.getElementById('pw-sidebar-toggle')!;
            toggleBtn.click();
            // Sidebar should not get pw-sidebar-hidden from the toggle
            expect(sidebar().classList.contains('pw-sidebar-hidden')).toBe(false);
        });
    });

    describe('setFeatures', () => {
        it('renders feature list items', () => {
            const entries = [
                makeEntry({ props: { id: 1, name: 'Pole A', url: '/s/1/', structure_type: 'pole' } }),
                makeEntry({ props: { id: 2, name: 'Pole B', url: '/s/2/', structure_type: 'pole' } }),
            ];
            Sidebar.setFeatures(entries);
            const items = document.querySelectorAll('.pw-list-item');
            expect(items.length).toBe(2);
        });

        it('updates feature count badge', () => {
            const entries = [
                makeEntry({ props: { id: 1, name: 'Pole A', url: '/s/1/', structure_type: 'pole' } }),
            ];
            Sidebar.setFeatures(entries);
            expect(countEl().textContent).toBe('1');
            expect(countEl().style.display).toBe('');
        });

        it('hides count badge when no features', () => {
            Sidebar.setFeatures([]);
            expect(countEl().textContent).toBe('0');
            expect(countEl().style.display).toBe('none');
        });

        it('preserves selection across data reloads', () => {
            const entry1 = makeEntry({ props: { id: 1, name: 'Pole A', url: '/s/1/', structure_type: 'pole' } });
            Sidebar.setFeatures([entry1]);
            Sidebar.selectFeature(entry1);

            // Reload with same feature (simulates moveend)
            const entry1b = makeEntry({ props: { id: 1, name: 'Pole A', url: '/s/1/', structure_type: 'pole' } });
            Sidebar.setFeatures([entry1b]);

            // Detail panel should still be visible (selection preserved)
            expect(detailPanelEl().style.display).toBe('');
        });

        it('calls showList in normal mode', () => {
            Sidebar.setFeatures([makeEntry()]);
            // showList expands list body
            expect(listBodyEl().classList.contains('collapsed')).toBe(false);
        });
    });

    describe('Escape key', () => {
        it('returns from detail to list', () => {
            Sidebar.showDetail(makeEntry());
            expect(detailPanelEl().style.display).toBe('');

            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
            expect(detailPanelEl().style.display).toBe('none');
        });
    });

    describe('back button', () => {
        it('returns from detail to list', () => {
            Sidebar.showDetail(makeEntry());
            const backBtn = document.getElementById('pw-detail-back')!;
            backBtn.click();
            expect(detailPanelEl().style.display).toBe('none');
            expect(listBodyEl().classList.contains('collapsed')).toBe(false);
        });
    });
});

// ---------------------------------------------------------------------------
// Tests — Kiosk mode
// ---------------------------------------------------------------------------

describe('Sidebar (kiosk mode)', () => {
    let map: ReturnType<typeof createMockMap>;

    beforeEach(() => {
        buildDOM(true);
        mockDeps();
        map = createMockMap();
        Sidebar.init(map as any, true);
    });

    describe('show / hide', () => {
        it('show() adds pw-sidebar-open class', () => {
            Sidebar.show();
            expect(sidebar().classList.contains('pw-sidebar-open')).toBe(true);
        });

        it('hide() removes pw-sidebar-open class', () => {
            sidebar().classList.add('pw-sidebar-open');
            Sidebar.hide();
            expect(sidebar().classList.contains('pw-sidebar-open')).toBe(false);
        });

        it('show() does NOT touch pw-sidebar-hidden', () => {
            Sidebar.show();
            expect(sidebar().classList.contains('pw-sidebar-hidden')).toBe(false);
        });
    });

    describe('showList / showDetail', () => {
        it('showList() opens kiosk sidebar', () => {
            Sidebar.showList();
            expect(sidebar().classList.contains('pw-sidebar-open')).toBe(true);
            expect(detailPanelEl().style.display).toBe('none');
        });

        it('showDetail() opens kiosk sidebar', () => {
            Sidebar.showDetail(makeEntry());
            expect(sidebar().classList.contains('pw-sidebar-open')).toBe(true);
            expect(detailPanelEl().style.display).toBe('');
        });
    });

    describe('Escape key closes kiosk sidebar', () => {
        it('removes pw-sidebar-open on Escape', () => {
            Sidebar.show();
            expect(sidebar().classList.contains('pw-sidebar-open')).toBe(true);

            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
            expect(sidebar().classList.contains('pw-sidebar-open')).toBe(false);
        });
    });

    describe('kiosk close button', () => {
        it('closes sidebar and hides detail', () => {
            Sidebar.showDetail(makeEntry());
            expect(sidebar().classList.contains('pw-sidebar-open')).toBe(true);

            const closeBtn = document.getElementById('pw-kiosk-close')!;
            closeBtn.click();
            expect(sidebar().classList.contains('pw-sidebar-open')).toBe(false);
            expect(detailPanelEl().style.display).toBe('none');
        });
    });

    describe('setFeatures does NOT auto-open sidebar', () => {
        it('sidebar stays closed on feature data reload', () => {
            Sidebar.setFeatures([makeEntry()]);
            // In kiosk mode, setFeatures should NOT call showList
            expect(sidebar().classList.contains('pw-sidebar-open')).toBe(false);
        });
    });
});

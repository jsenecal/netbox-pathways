/**
 * Tests for the map-utils module.
 *
 * Covers pure utility functions (titleCase, esc, haversine, debounce,
 * getCookie, bboxParam) and the color/shape/icon constants and factories.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
    STRUCTURE_COLORS,
    STRUCTURE_SHAPES,
    PATHWAY_COLORS,
    structureIcon,
    clusterIcon,
    esc,
    titleCase,
    getCookie,
    bboxParam,
    debounce,
    haversine,
} from './map-utils';

// ---------------------------------------------------------------------------
// Stub Leaflet globals
// ---------------------------------------------------------------------------

let lastDivIconArgs: any = null;

(globalThis as any).L = {
    divIcon: vi.fn((opts: any) => {
        lastDivIconArgs = opts;
        return { options: opts };
    }),
};

// ---------------------------------------------------------------------------
// titleCase
// ---------------------------------------------------------------------------

describe('titleCase', () => {
    it('converts snake_case to Title Case', () => {
        expect(titleCase('building_entrance')).toBe('Building Entrance');
    });

    it('handles single word', () => {
        expect(titleCase('pole')).toBe('Pole');
    });

    it('handles empty string', () => {
        expect(titleCase('')).toBe('');
    });

    it('handles null-ish values via fallback', () => {
        // The function uses (str || '') so null/undefined become ''
        expect(titleCase(null as unknown as string)).toBe('');
        expect(titleCase(undefined as unknown as string)).toBe('');
    });

    it('handles triple underscore word', () => {
        expect(titleCase('a_b_c')).toBe('A B C');
    });

    it('handles already capitalized input', () => {
        expect(titleCase('Already Good')).toBe('Already Good');
    });

    it('capitalizes first letter of each word after underscore replacement', () => {
        expect(titleCase('direct_buried')).toBe('Direct Buried');
    });
});

// ---------------------------------------------------------------------------
// esc (HTML escape)
// ---------------------------------------------------------------------------

describe('esc', () => {
    it('escapes angle brackets', () => {
        expect(esc('<script>alert("xss")</script>')).toBe(
            '&lt;script&gt;alert("xss")&lt;/script&gt;'
        );
    });

    it('escapes ampersands', () => {
        expect(esc('A & B')).toBe('A &amp; B');
    });

    it('passes normal text through unchanged', () => {
        expect(esc('Hello World')).toBe('Hello World');
    });

    it('returns empty string for empty input', () => {
        expect(esc('')).toBe('');
    });

    it('escapes multiple special characters', () => {
        const result = esc('<a href="x">&</a>');
        expect(result).toContain('&lt;');
        expect(result).toContain('&gt;');
        expect(result).toContain('&amp;');
    });
});

// ---------------------------------------------------------------------------
// haversine
// ---------------------------------------------------------------------------

describe('haversine', () => {
    it('returns 0 for same point', () => {
        expect(haversine(45.5, -73.5, 45.5, -73.5)).toBe(0);
    });

    it('computes Montreal to NYC distance (~530 km)', () => {
        // Montreal: 45.5017, -73.5673
        // NYC:      40.7128, -74.0060
        const dist = haversine(45.5017, -73.5673, 40.7128, -74.0060);
        // Should be approximately 530-535 km
        expect(dist).toBeGreaterThan(525_000);
        expect(dist).toBeLessThan(540_000);
    });

    it('computes antipodal points distance (~20015 km, half circumference)', () => {
        // North pole to south pole
        const dist = haversine(90, 0, -90, 0);
        // Half Earth circumference ~ 20,015 km
        expect(dist).toBeGreaterThan(20_000_000);
        expect(dist).toBeLessThan(20_100_000);
    });

    it('is symmetric', () => {
        const ab = haversine(48.8566, 2.3522, 51.5074, -0.1278);
        const ba = haversine(51.5074, -0.1278, 48.8566, 2.3522);
        expect(Math.abs(ab - ba)).toBeLessThan(0.01);
    });

    it('handles equator crossing', () => {
        // 1 degree of latitude ~ 111 km
        const dist = haversine(1, 0, -1, 0);
        expect(dist).toBeGreaterThan(220_000);
        expect(dist).toBeLessThan(224_000);
    });
});

// ---------------------------------------------------------------------------
// debounce
// ---------------------------------------------------------------------------

describe('debounce', () => {
    beforeEach(() => {
        vi.useFakeTimers();
    });

    it('delays execution by the specified delay', () => {
        const fn = vi.fn();
        const debounced = debounce(fn, 200);
        debounced();
        expect(fn).not.toHaveBeenCalled();
        vi.advanceTimersByTime(200);
        expect(fn).toHaveBeenCalledOnce();
    });

    it('resets timer on subsequent calls', () => {
        const fn = vi.fn();
        const debounced = debounce(fn, 200);
        debounced();
        vi.advanceTimersByTime(100);
        debounced(); // reset
        vi.advanceTimersByTime(100);
        expect(fn).not.toHaveBeenCalled();
        vi.advanceTimersByTime(100);
        expect(fn).toHaveBeenCalledOnce();
    });

    it('only fires once for rapid calls', () => {
        const fn = vi.fn();
        const debounced = debounce(fn, 100);
        for (let i = 0; i < 10; i++) debounced();
        vi.advanceTimersByTime(100);
        expect(fn).toHaveBeenCalledOnce();
    });

    it('fires immediately when delay is 0 (after microtask)', () => {
        const fn = vi.fn();
        const debounced = debounce(fn, 0);
        debounced();
        vi.advanceTimersByTime(0);
        expect(fn).toHaveBeenCalledOnce();
    });
});

// ---------------------------------------------------------------------------
// getCookie
// ---------------------------------------------------------------------------

describe('getCookie', () => {
    beforeEach(() => {
        // Reset cookie to empty
        Object.defineProperty(document, 'cookie', {
            writable: true,
            value: '',
        });
    });

    it('returns null when no cookies exist', () => {
        expect(getCookie('csrftoken')).toBeNull();
    });

    it('extracts a cookie value', () => {
        document.cookie = 'csrftoken=abc123; sessionid=xyz';
        expect(getCookie('csrftoken')).toBe('abc123');
    });

    it('extracts a later cookie', () => {
        document.cookie = 'csrftoken=abc123; sessionid=xyz';
        expect(getCookie('sessionid')).toBe('xyz');
    });

    it('returns null for a missing cookie name', () => {
        document.cookie = 'csrftoken=abc123';
        expect(getCookie('missing')).toBeNull();
    });
});

// ---------------------------------------------------------------------------
// bboxParam
// ---------------------------------------------------------------------------

describe('bboxParam', () => {
    it('returns "west,south,east,north" from map bounds', () => {
        const mockMap = {
            getBounds: vi.fn(() => ({
                getWest: () => -74.0,
                getSouth: () => 40.7,
                getEast: () => -73.5,
                getNorth: () => 45.5,
            })),
        };
        expect(bboxParam(mockMap as any)).toBe('-74,40.7,-73.5,45.5');
    });
});

// ---------------------------------------------------------------------------
// STRUCTURE_COLORS
// ---------------------------------------------------------------------------

describe('STRUCTURE_COLORS', () => {
    const expectedTypes = [
        'pole', 'manhole', 'handhole', 'cabinet', 'vault', 'pedestal',
        'building_entrance', 'splice_closure', 'tower', 'roof',
        'equipment_room', 'telecom_closet', 'riser_room',
    ];

    it('has all 13 structure types', () => {
        expect(Object.keys(STRUCTURE_COLORS)).toHaveLength(13);
    });

    it.each(expectedTypes)('has color for %s', (type) => {
        expect(STRUCTURE_COLORS[type]).toBeDefined();
    });

    it('all values are hex color strings', () => {
        for (const color of Object.values(STRUCTURE_COLORS)) {
            expect(color).toMatch(/^#[0-9a-f]{6}$/i);
        }
    });
});

// ---------------------------------------------------------------------------
// STRUCTURE_SHAPES
// ---------------------------------------------------------------------------

describe('STRUCTURE_SHAPES', () => {
    const expectedTypes = [
        'pole', 'manhole', 'handhole', 'cabinet', 'vault', 'pedestal',
        'building_entrance', 'splice_closure', 'tower', 'roof',
        'equipment_room', 'telecom_closet', 'riser_room',
    ];

    it('has all 13 structure types', () => {
        expect(Object.keys(STRUCTURE_SHAPES)).toHaveLength(13);
    });

    it.each(expectedTypes)('has SVG shape for %s', (type) => {
        expect(STRUCTURE_SHAPES[type]).toBeDefined();
    });

    it('all shapes contain SVG elements', () => {
        for (const shape of Object.values(STRUCTURE_SHAPES)) {
            // Should contain at least one SVG element tag
            expect(shape).toMatch(/<(circle|rect|polygon|line|path)\s/);
        }
    });

    it('keys match STRUCTURE_COLORS keys', () => {
        const colorKeys = Object.keys(STRUCTURE_COLORS).sort();
        const shapeKeys = Object.keys(STRUCTURE_SHAPES).sort();
        expect(shapeKeys).toEqual(colorKeys);
    });
});

// ---------------------------------------------------------------------------
// PATHWAY_COLORS
// ---------------------------------------------------------------------------

describe('PATHWAY_COLORS', () => {
    const expectedTypes = [
        'conduit', 'conduit_bank', 'aerial', 'direct_buried',
        'innerduct', 'microduct', 'tray', 'raceway', 'submarine',
    ];

    it('has all 9 pathway types', () => {
        expect(Object.keys(PATHWAY_COLORS)).toHaveLength(9);
    });

    it.each(expectedTypes)('has color for %s', (type) => {
        expect(PATHWAY_COLORS[type]).toBeDefined();
    });

    it('all values are hex color strings', () => {
        for (const color of Object.values(PATHWAY_COLORS)) {
            expect(color).toMatch(/^#[0-9a-f]{6}$/i);
        }
    });
});

// ---------------------------------------------------------------------------
// structureIcon
// ---------------------------------------------------------------------------

describe('structureIcon', () => {
    beforeEach(() => {
        lastDivIconArgs = null;
    });

    it('returns an icon with default size 20', () => {
        structureIcon('pole');
        expect(lastDivIconArgs.iconSize).toEqual([20, 20]);
    });

    it('returns an icon with custom size', () => {
        structureIcon('manhole', 30);
        expect(lastDivIconArgs.iconSize).toEqual([30, 30]);
    });

    it('sets iconAnchor to half the size', () => {
        structureIcon('cabinet', 40);
        expect(lastDivIconArgs.iconAnchor).toEqual([20, 20]);
    });

    it('sets className to pw-marker', () => {
        structureIcon('pole');
        expect(lastDivIconArgs.className).toBe('pw-marker');
    });

    it('includes SVG html with the correct color', () => {
        structureIcon('pole');
        expect(lastDivIconArgs.html).toContain('#2e7d32');
    });

    it('uses fallback color for unknown type', () => {
        structureIcon('unknown_type');
        expect(lastDivIconArgs.html).toContain('#616161');
    });

    it('uses fallback shape for unknown type', () => {
        structureIcon('unknown_type');
        expect(lastDivIconArgs.html).toContain('<circle cx="10" cy="10" r="8"/>');
    });

    it('uses outline stroke for fill="none" shapes', () => {
        // pole shape includes fill="none", so stroke should be the type color
        structureIcon('pole');
        expect(lastDivIconArgs.html).toContain('stroke="#2e7d32"');
    });

    it('uses white stroke for filled shapes', () => {
        // manhole is a filled circle (no fill="none")
        structureIcon('manhole');
        expect(lastDivIconArgs.html).toContain('stroke="white"');
    });
});

// ---------------------------------------------------------------------------
// clusterIcon
// ---------------------------------------------------------------------------

describe('clusterIcon', () => {
    beforeEach(() => {
        lastDivIconArgs = null;
    });

    it('uses small class for count < 10', () => {
        clusterIcon(5);
        expect(lastDivIconArgs.html).toContain('pw-cluster-small');
        expect(lastDivIconArgs.iconSize).toEqual([34, 34]);
    });

    it('uses medium class for count 10-99', () => {
        clusterIcon(50);
        expect(lastDivIconArgs.html).toContain('pw-cluster-medium');
        expect(lastDivIconArgs.iconSize).toEqual([40, 40]);
    });

    it('uses large class for count >= 100', () => {
        clusterIcon(100);
        expect(lastDivIconArgs.html).toContain('pw-cluster-large');
        expect(lastDivIconArgs.iconSize).toEqual([46, 46]);
    });

    it('boundary: count=9 is small', () => {
        clusterIcon(9);
        expect(lastDivIconArgs.html).toContain('pw-cluster-small');
    });

    it('boundary: count=10 is medium', () => {
        clusterIcon(10);
        expect(lastDivIconArgs.html).toContain('pw-cluster-medium');
    });

    it('boundary: count=99 is medium', () => {
        clusterIcon(99);
        expect(lastDivIconArgs.html).toContain('pw-cluster-medium');
    });

    it('displays the count in the HTML', () => {
        clusterIcon(42);
        expect(lastDivIconArgs.html).toContain('>42<');
    });

    it('sets className to pw-server-cluster', () => {
        clusterIcon(1);
        expect(lastDivIconArgs.className).toBe('pw-server-cluster');
    });

    it('centers the icon anchor', () => {
        clusterIcon(5);
        expect(lastDivIconArgs.iconAnchor).toEqual([17, 17]); // 34/2
    });
});

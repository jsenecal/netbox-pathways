/**
 * Tests for the locked endpoint markers module.
 *
 * Focus: name labels on the locked start/end markers, matching the
 * reference-layer label styling (permanent, right of the marker).
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { addLockedGeometry, fitPath } from './endpoint-markers';

function createMockLayer(type: string) {
    const layer: any = { _type: type };
    layer.addTo = vi.fn(() => layer);
    layer.bindTooltip = vi.fn(() => layer);
    return layer;
}

(globalThis as any).L = {
    circleMarker: vi.fn(() => createMockLayer('circleMarker')),
    polygon: vi.fn(() => createMockLayer('polygon')),
    point: vi.fn((x: number, y: number) => ({ x, y })),
    latLng: vi.fn((lat: number, lng: number) => ({ lat, lng })),
};

const mockMap = {} as L.Map;

const POINT: GeoJSON.Geometry = { type: 'Point', coordinates: [-73.55, 45.45] };
const POLYGON: GeoJSON.Geometry = {
    type: 'Polygon',
    coordinates: [[[0, 0], [0, 1], [1, 1], [0, 0]]],
};

beforeEach(() => {
    vi.clearAllMocks();
});

describe('addLockedGeometry labels', () => {
    it('labels a point endpoint with its structure name', () => {
        addLockedGeometry(mockMap, POINT, 'MH-100');
        const layer = (L.circleMarker as ReturnType<typeof vi.fn>).mock.results[0].value;
        expect(layer.bindTooltip).toHaveBeenCalledTimes(1);
        const [content, opts] = layer.bindTooltip.mock.calls[0];
        expect(content).toBe('MH-100');
        expect(opts.permanent).toBe(true);
        expect(opts.direction).toBe('right');
        expect(opts.className).toContain('pw-ref-label');
    });

    it('labels a polygon endpoint with its structure name', () => {
        addLockedGeometry(mockMap, POLYGON, 'Vault 7');
        const layer = (L.polygon as ReturnType<typeof vi.fn>).mock.results[0].value;
        expect(layer.bindTooltip).toHaveBeenCalledTimes(1);
        expect(layer.bindTooltip.mock.calls[0][0]).toBe('Vault 7');
    });

    it('escapes HTML in structure names', () => {
        addLockedGeometry(mockMap, POINT, '<b>MH</b>');
        const layer = (L.circleMarker as ReturnType<typeof vi.fn>).mock.results[0].value;
        expect(layer.bindTooltip.mock.calls[0][0]).toBe('&lt;b&gt;MH&lt;/b&gt;');
    });

    it('adds no label when the name is missing', () => {
        addLockedGeometry(mockMap, POINT);
        const layer = (L.circleMarker as ReturnType<typeof vi.fn>).mock.results[0].value;
        expect(layer.bindTooltip).not.toHaveBeenCalled();
    });
});

describe('fitPath', () => {
    const POLE: GeoJSON.Geometry = { type: 'Point', coordinates: [10, 0] };
    // Square building spanning lng 0..1, lat 0..1.
    const BUILDING: GeoJSON.Geometry = {
        type: 'Polygon',
        coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
    };

    it('snaps the ends and keeps interior vertices when not straight', () => {
        const fitted = fitPath([[0.5, 2], [3, 5], [0.2, 9.5]], { start: BUILDING, end: POLE }, false);
        expect(fitted).toEqual([[0.5, 1], [3, 5], [0, 10]]);
    });

    it('collapses to the two landings when straight', () => {
        const fitted = fitPath([[0.5, 2], [3, 5], [4, 6], [0.2, 9.5]], { start: BUILDING, end: POLE }, true);
        expect(fitted).toEqual([[0.5, 1], [0, 10]]);
    });

    it('keeps an unanchored end where it was drawn', () => {
        const fitted = fitPath([[0.5, 2], [3, 5], [7, 7]], { start: BUILDING }, true);
        expect(fitted).toEqual([[0.5, 1], [7, 7]]);
    });
});

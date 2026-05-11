/**
 * Tests for geom-ops.
 *
 * Pure-function state machine that decides what happens when a point is
 * appended to a LineString widget via the helper buttons. See issue #32.
 */

import { describe, it, expect } from 'vitest';
import { computeAppendVertex } from './geom-ops';

describe('computeAppendVertex - extends an existing line', () => {
    it('appends a vertex to a 2-point line', () => {
        const line: GeoJSON.LineString = {
            type: 'LineString',
            coordinates: [[-73.5, 45.5], [-73.4, 45.6]],
        };
        const r = computeAppendVertex(line, null, [-73.3, 45.7]);
        expect(r.kind).toBe('extended');
        expect(r.geometry).toEqual({
            type: 'LineString',
            coordinates: [[-73.5, 45.5], [-73.4, 45.6], [-73.3, 45.7]],
        });
        expect(r.pending).toBeNull();
    });

    it('appends to a 3-point line, preserving order', () => {
        const line: GeoJSON.LineString = {
            type: 'LineString',
            coordinates: [[0, 0], [1, 1], [2, 2]],
        };
        const r = computeAppendVertex(line, null, [3, 3]);
        expect(r.kind).toBe('extended');
        expect((r.geometry as GeoJSON.LineString).coordinates).toEqual([
            [0, 0], [1, 1], [2, 2], [3, 3],
        ]);
    });

    it('discards a pending point if a line already exists', () => {
        const line: GeoJSON.LineString = {
            type: 'LineString',
            coordinates: [[-73.5, 45.5], [-73.4, 45.6]],
        };
        const r = computeAppendVertex(line, [-100, 50], [-73.3, 45.7]);
        expect(r.kind).toBe('extended');
        expect(r.pending).toBeNull();
        // The stale pending point is not added to the line.
        expect((r.geometry as GeoJSON.LineString).coordinates).toEqual([
            [-73.5, 45.5], [-73.4, 45.6], [-73.3, 45.7],
        ]);
    });
});

describe('computeAppendVertex - materializes from pending', () => {
    it('starts a 2-vertex line when pending exists and no line', () => {
        const r = computeAppendVertex(null, [-73.5, 45.5], [-73.4, 45.6]);
        expect(r.kind).toBe('started');
        expect(r.geometry).toEqual({
            type: 'LineString',
            coordinates: [[-73.5, 45.5], [-73.4, 45.6]],
        });
        expect(r.pending).toBeNull();
    });
});

describe('computeAppendVertex - stashes first point as pending', () => {
    it('returns pending when no line and no prior pending', () => {
        const r = computeAppendVertex(null, null, [-73.5, 45.5]);
        expect(r.kind).toBe('pending');
        expect(r.geometry).toBeNull();
        expect(r.pending).toEqual([-73.5, 45.5]);
    });

    it('replaces an existing Point with a pending first vertex', () => {
        // If the user previously placed a Point (e.g., on a Geometry widget,
        // then changed the form type), treat it as no-line and stash.
        const pt: GeoJSON.Point = { type: 'Point', coordinates: [-73.5, 45.5] };
        const r = computeAppendVertex(pt, null, [-73.4, 45.6]);
        expect(r.kind).toBe('pending');
        expect(r.pending).toEqual([-73.4, 45.6]);
    });
});

/**
 * Tests for the map widget field module.
 *
 * Focus: the widget's minimum zoom floor -- editing a single geometry never
 * needs a world-level view, so the widget clamps zoom-out independently of
 * the full-page map's minZoom.
 */

import { describe, it, expect } from 'vitest';
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

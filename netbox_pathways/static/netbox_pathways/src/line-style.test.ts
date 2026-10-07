import { describe, it, expect } from 'vitest';
import { lineStyle } from './line-style';

describe('lineStyle', () => {
    it('draws a plain line in its colour', () => {
        expect(lineStyle({ color: 'brown' })).toEqual({ color: 'brown', weight: 4, opacity: 0.8 });
    });

    it('dashes gap lines', () => {
        expect(lineStyle({ color: 'red', dashed: true }).dashArray).toBe('8 6');
    });

    it('thickens the highlighted line and dims the others', () => {
        const highlighted = lineStyle({ color: 'green', key: 'segment-2' }, 'segment-2');
        const other = lineStyle({ color: 'green', key: 'segment-3' }, 'segment-2');
        expect([highlighted.weight, highlighted.opacity]).toEqual([7, 1]);
        expect(other.opacity).toBe(0.25);
    });
});

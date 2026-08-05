import { describe, it, expect, beforeEach } from 'vitest';
import { OccupancyPrefs } from './occupancy-prefs';

describe('OccupancyPrefs', () => {
    beforeEach(() => {
        localStorage.clear();
    });

    describe('hide toggle', () => {
        it('defaults to off', () => {
            expect(OccupancyPrefs.isHideUnoccupied()).toBe(false);
        });

        it('persists across reads', () => {
            OccupancyPrefs.setHideUnoccupied(true);
            expect(OccupancyPrefs.isHideUnoccupied()).toBe(true);
            OccupancyPrefs.setHideUnoccupied(false);
            expect(OccupancyPrefs.isHideUnoccupied()).toBe(false);
        });
    });

    describe('occupiedParam', () => {
        it('is null while hiding is off', () => {
            expect(OccupancyPrefs.occupiedParam()).toBeNull();
        });

        it('is "true" when hiding is on', () => {
            OccupancyPrefs.setHideUnoccupied(true);
            expect(OccupancyPrefs.occupiedParam()).toBe('true');
        });
    });
});

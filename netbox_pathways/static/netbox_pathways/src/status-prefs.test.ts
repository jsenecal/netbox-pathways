import { describe, it, expect, beforeEach } from 'vitest';
import { StatusPrefs, DEFAULT_INACTIVE } from './status-prefs';

describe('StatusPrefs', () => {
    beforeEach(() => {
        localStorage.clear();
        StatusPrefs.setAvailableStatuses([]);
    });

    describe('hide toggle', () => {
        it('defaults to off', () => {
            expect(StatusPrefs.isHideInactive()).toBe(false);
        });

        it('persists across reads', () => {
            StatusPrefs.setHideInactive(true);
            expect(StatusPrefs.isHideInactive()).toBe(true);
            StatusPrefs.setHideInactive(false);
            expect(StatusPrefs.isHideInactive()).toBe(false);
        });
    });

    describe('inactive set', () => {
        it('defaults to retired + abandoned', () => {
            expect(StatusPrefs.getInactiveSet()).toEqual(DEFAULT_INACTIVE);
        });

        it('persists a custom set', () => {
            StatusPrefs.setInactiveSet(['decommissioning']);
            expect(StatusPrefs.getInactiveSet()).toEqual(['decommissioning']);
        });

        it('falls back to default on corrupt storage', () => {
            localStorage.setItem('pw_inactive_statuses', 'not json');
            expect(StatusPrefs.getInactiveSet()).toEqual(DEFAULT_INACTIVE);
        });
    });

    describe('excludeParam', () => {
        it('is null while hiding is off', () => {
            expect(StatusPrefs.excludeParam()).toBeNull();
        });

        it('joins the inactive set when hiding is on', () => {
            StatusPrefs.setHideInactive(true);
            expect(StatusPrefs.excludeParam()).toBe('retired,abandoned');
        });

        it('is null when the inactive set is empty', () => {
            StatusPrefs.setHideInactive(true);
            StatusPrefs.setInactiveSet([]);
            expect(StatusPrefs.excludeParam()).toBeNull();
        });
    });

    describe('available statuses', () => {
        it('resolves colors by value', () => {
            StatusPrefs.setAvailableStatuses([
                { value: 'active', label: 'Active', color: 'green' },
                { value: 'retired', label: 'Retired', color: 'red' },
            ]);
            expect(StatusPrefs.colorFor('retired')).toBe('red');
            expect(StatusPrefs.colorFor('unknown')).toBeNull();
        });

        it('ignores non-array payloads', () => {
            StatusPrefs.setAvailableStatuses([{ value: 'active', label: 'Active', color: 'green' }]);
            StatusPrefs.setAvailableStatuses(undefined);
            expect(StatusPrefs.getAvailableStatuses()).toHaveLength(1);
        });
    });
});

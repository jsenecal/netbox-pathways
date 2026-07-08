/**
 * Tests for the load-strategy decision the map uses on every pan/zoom.
 *
 * The strategy splits the zoom axis into three bands:
 *
 *   zoom < MIN_DATA_ZOOM            -> render nothing
 *   MIN_DATA_ZOOM <= z < SKIP_INFO  -> use cached /info optimistically if
 *                                      any, else gated /info round-trip
 *   zoom >= SKIP_INFO_ZOOM          -> skip /info entirely
 *
 * The whole point is to avoid blocking on /info when the viewport is small
 * enough that thresholds are unreachable, or when a recent /info result is
 * already cached. The revalidation that runs in the background reconciles
 * the optimistic render if counts shifted enough to flip a decision.
 */

import { describe, it, expect } from 'vitest';
import {
    chooseLoadStrategy,
    decideSkipInfo,
    decisionsDiffer,
    MIN_DATA_ZOOM,
    SKIP_INFO_ZOOM,
} from './load-strategy';
import type { MapInfo, RenderingDecision } from './data-layers';

function makeInfo(overrides: Partial<MapInfo> = {}): MapInfo {
    return {
        bbox: null,
        counts: {
            structures: 50,
            conduit_banks: 10,
            conduits: 20,
            aerial_spans: 5,
            direct_buried: 0,
            circuits: 0,
        },
        thresholds: {
            structures: { cluster: 200, hide: 5000 },
            conduit_banks: { hide: 500 },
            conduits: { hide: 500 },
            aerial_spans: { hide: 500 },
            direct_buried: { hide: 500 },
            circuits: { hide: 500 },
        },
        ...overrides,
    };
}

describe('chooseLoadStrategy', () => {
    const enabled = new Set(['structures', 'conduits', 'aerial_spans']);

    it('below MIN_DATA_ZOOM, returns below-min-zoom strategy', () => {
        const s = chooseLoadStrategy(MIN_DATA_ZOOM - 1, null, enabled);
        expect(s.kind).toBe('below-min-zoom');
    });

    it('at or above SKIP_INFO_ZOOM, skips /info entirely', () => {
        const s = chooseLoadStrategy(SKIP_INFO_ZOOM, null, enabled);
        expect(s.kind).toBe('skip-info');
        // No info round-trip needed; caller renders the skip-info decision now.
        if (s.kind !== 'skip-info') throw new Error('strategy kind regression');
        expect(s.decision.clusterMode).toBe('off');
        expect(s.decision.layers.structures).toBe('render');
        expect(s.decision.layers.conduits).toBe('render');
    });

    it('above SKIP_INFO_ZOOM, even a stale cached info does not gate rendering', () => {
        // Cached info from a denser, lower-zoom viewport saying "hide everything"
        // would otherwise suppress; the skip-info band overrides because the
        // small viewport at high zoom cannot plausibly carry that many features.
        const cachedDense = makeInfo({
            counts: {
                structures: 10000,
                conduit_banks: 10,
                conduits: 20,
                aerial_spans: 5,
                direct_buried: 0,
                circuits: 0,
            },
        });
        const s = chooseLoadStrategy(SKIP_INFO_ZOOM + 2, cachedDense, enabled);
        expect(s.kind).toBe('skip-info');
        if (s.kind !== 'skip-info') throw new Error('strategy kind regression');
        expect(s.decision.clusterMode).toBe('off');
        expect(s.decision.layers.structures).toBe('render');
        expect(s.decision.layers.conduits).toBe('render');
    });

    it('inside the gated band with a cached info, returns optimistic + revalidate', () => {
        const cached = makeInfo();
        const s = chooseLoadStrategy(13, cached, enabled);
        expect(s.kind).toBe('optimistic');
        if (s.kind !== 'optimistic') throw new Error('strategy kind regression');
        expect(s.cachedInfo).toBe(cached);
        expect(s.revalidate).toBe(true);
        expect(s.decision.layers.structures).toBe('render');
    });

    it('inside the gated band without a cached info, returns gated', () => {
        const s = chooseLoadStrategy(13, null, enabled);
        expect(s.kind).toBe('gated');
    });

    it('lets the caller override SKIP_INFO_ZOOM (server-side config)', () => {
        // If a deployment configures map_skip_info_zoom: 19, zoom 17 is no
        // longer in the skip-info band -- gated/optimistic flow applies.
        const s = chooseLoadStrategy(17, null, enabled, 19);
        expect(s.kind).toBe('gated');
        const s2 = chooseLoadStrategy(19, null, enabled, 19);
        expect(s2.kind).toBe('skip-info');
    });
});

describe('decideSkipInfo', () => {
    it('renders every enabled native key and no others', () => {
        const d: RenderingDecision = decideSkipInfo(new Set(['structures', 'conduits']));
        expect(d.clusterMode).toBe('off');
        expect(d.layers.structures).toBe('render');
        expect(d.layers.conduits).toBe('render');
        expect(d.layers.conduit_banks).toBeUndefined();
        expect(d.layers.aerial_spans).toBeUndefined();
    });

    it('passes external layer keys through unchanged', () => {
        const d = decideSkipInfo(new Set(['structures', 'external:splices']));
        expect(d.layers['external:splices']).toBe('render');
    });
});

describe('decisionsDiffer', () => {
    const base: RenderingDecision = {
        clusterMode: 'off',
        layers: { structures: 'render', conduits: 'render' },
    };

    it('returns false for identical decisions', () => {
        const a = { ...base, layers: { ...base.layers } };
        const b = { ...base, layers: { ...base.layers } };
        expect(decisionsDiffer(a, b)).toBe(false);
    });

    it('returns true when cluster mode flips', () => {
        const a = base;
        const b: RenderingDecision = { ...base, clusterMode: 'client' };
        expect(decisionsDiffer(a, b)).toBe(true);
    });

    it('returns true when a layer flips render -> hide', () => {
        const a = base;
        const b: RenderingDecision = {
            clusterMode: 'off',
            layers: { structures: 'render', conduits: 'hide' },
        };
        expect(decisionsDiffer(a, b)).toBe(true);
    });

    it('returns true when the set of layers changes', () => {
        const a = base;
        const b: RenderingDecision = {
            clusterMode: 'off',
            layers: { structures: 'render', conduits: 'render', aerial_spans: 'render' },
        };
        expect(decisionsDiffer(a, b)).toBe(true);
    });
});

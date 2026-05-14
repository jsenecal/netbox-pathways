/**
 * Tests for the pure decision function that maps /info counts + thresholds
 * to a per-layer render decision plus a global cluster mode.
 *
 * The "structures clustered -> no supports" rule lives here: whenever
 * structures cross either threshold (client cluster or hide), all
 * non-structure layers are suppressed regardless of their own counts.
 */

import { describe, it, expect } from 'vitest';
import { decideLayerRendering } from './data-layers';
import type { MapInfo } from './data-layers';

function makeInfo(overrides: Partial<MapInfo> = {}): MapInfo {
    return {
        bbox: null,
        counts: {
            structures: 0,
            conduit_banks: 0,
            conduits: 0,
            aerial_spans: 0,
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

describe('decideLayerRendering', () => {
    it('renders everything when all counts are below threshold', () => {
        const info = makeInfo({
            counts: { structures: 50, conduit_banks: 10, conduits: 20, aerial_spans: 5, direct_buried: 0, circuits: 0 },
        });
        const d = decideLayerRendering(info, new Set(['structures', 'conduit_banks', 'conduits', 'aerial_spans']));
        expect(d.clusterMode).toBe('off');
        expect(d.layers.structures).toBe('render');
        expect(d.layers.conduit_banks).toBe('render');
        expect(d.layers.conduits).toBe('render');
        expect(d.layers.aerial_spans).toBe('render');
    });

    it('switches to client cluster mode and suppresses supports', () => {
        const info = makeInfo({
            counts: { structures: 1000, conduit_banks: 10, conduits: 20, aerial_spans: 5, direct_buried: 0, circuits: 0 },
        });
        const d = decideLayerRendering(info, new Set(['structures', 'conduit_banks', 'conduits']));
        expect(d.clusterMode).toBe('client');
        // Even though banks/conduits are well under their own hide threshold,
        // they're suppressed because structures are clustered.
        expect(d.layers.structures).toBe('render');
        expect(d.layers.conduit_banks).toBe('hide');
        expect(d.layers.conduits).toBe('hide');
    });

    it('switches to server cluster mode above the hide threshold', () => {
        const info = makeInfo({
            counts: { structures: 8000, conduit_banks: 10, conduits: 20, aerial_spans: 5, direct_buried: 0, circuits: 0 },
        });
        const d = decideLayerRendering(info, new Set(['structures', 'conduit_banks']));
        expect(d.clusterMode).toBe('server');
        expect(d.layers.structures).toBe('render');
        expect(d.layers.conduit_banks).toBe('hide');
    });

    it('hides per-layer when structures are off-cluster but support layer is over budget', () => {
        const info = makeInfo({
            counts: { structures: 50, conduit_banks: 800, conduits: 100, aerial_spans: 5, direct_buried: 0, circuits: 0 },
        });
        const d = decideLayerRendering(info, new Set(['structures', 'conduit_banks', 'conduits']));
        expect(d.clusterMode).toBe('off');
        expect(d.layers.conduit_banks).toBe('hide');
        expect(d.layers.conduits).toBe('render');
    });

    it('respects the enabled-layer set (disabled layers omitted)', () => {
        const info = makeInfo({
            counts: { structures: 50, conduit_banks: 100, conduits: 100, aerial_spans: 5, direct_buried: 0, circuits: 0 },
        });
        const d = decideLayerRendering(info, new Set(['structures']));
        expect(d.layers.structures).toBe('render');
        expect(d.layers.conduit_banks).toBeUndefined();
        expect(d.layers.conduits).toBeUndefined();
    });

    it('handles external reference-mode layers using their own threshold', () => {
        const info = makeInfo({
            counts: {
                structures: 50, conduit_banks: 10, conduits: 0, aerial_spans: 0,
                direct_buried: 0, circuits: 0,
                external: { splices: 30, otdr_traces: 1000 },
            },
            thresholds: {
                structures: { cluster: 200, hide: 5000 },
                conduit_banks: { hide: 500 },
                conduits: { hide: 500 },
                aerial_spans: { hide: 500 },
                direct_buried: { hide: 500 },
                circuits: { hide: 500 },
                external: { splices: { hide: 500 }, otdr_traces: { hide: 500 } },
            },
        });
        const d = decideLayerRendering(info, new Set(['structures', 'external:splices', 'external:otdr_traces']));
        expect(d.clusterMode).toBe('off');
        expect(d.layers['external:splices']).toBe('render');
        expect(d.layers['external:otdr_traces']).toBe('hide');
    });

    it('suppresses external layers when structures are clustered', () => {
        const info = makeInfo({
            counts: {
                structures: 1000, conduit_banks: 0, conduits: 0, aerial_spans: 0,
                direct_buried: 0, circuits: 0,
                external: { splices: 30 },
            },
            thresholds: {
                structures: { cluster: 200, hide: 5000 },
                conduit_banks: { hide: 500 },
                conduits: { hide: 500 },
                aerial_spans: { hide: 500 },
                direct_buried: { hide: 500 },
                circuits: { hide: 500 },
                external: { splices: { hide: 500 } },
            },
        });
        const d = decideLayerRendering(info, new Set(['structures', 'external:splices']));
        expect(d.clusterMode).toBe('client');
        expect(d.layers['external:splices']).toBe('hide');
    });
});

/**
 * Decides how to render the map at a given zoom + cache state.
 *
 * The map used to round-trip `/info` on every pan/zoom and only start the
 * GeoJSON fetches once the response came back. Even with conditional
 * revalidation (ETag + 304), that adds one full RTT per move which feels
 * noticeably laggy on a slow link.
 *
 * The strategy here cuts that latency in two ways:
 *
 *   1. Skip-info band (zoom >= SKIP_INFO_ZOOM): the viewport is small
 *      enough that hide/cluster thresholds are effectively unreachable.
 *      Skip `/info` entirely and synthesize a "render every enabled layer"
 *      decision.
 *
 *   2. Optimistic + revalidate (MIN_DATA_ZOOM <= zoom < SKIP_INFO_ZOOM
 *      with a cached `/info`): render the cached decision immediately and
 *      fire `/info` in the background with `If-None-Match`. A 304 means
 *      the optimistic render was correct -- nothing to do. A 200 with a
 *      meaningfully different decision triggers a single reconciliation
 *      reload.
 *
 *   3. Cold gated path (no cache): the original "wait for /info, then
 *      load" behaviour, used only on the very first viewport.
 */

import {
    MIN_DATA_ZOOM,
    SKIP_INFO_ZOOM,
    decideLayerRendering,
    decideSkipInfo,
} from './data-layers';
import type { MapInfo, RenderingDecision } from './data-layers';

export { MIN_DATA_ZOOM, SKIP_INFO_ZOOM, decideSkipInfo };

export type LoadStrategy =
    | { kind: 'below-min-zoom' }
    | { kind: 'skip-info'; decision: RenderingDecision }
    | { kind: 'optimistic'; decision: RenderingDecision; revalidate: true; cachedInfo: MapInfo }
    | { kind: 'gated' };

/**
 * Picks the strategy for one pan/zoom event.
 *
 * `skipInfoZoom` defaults to `SKIP_INFO_ZOOM` so it tracks server config;
 * the argument is mainly there for tests.
 */
export function chooseLoadStrategy(
    zoom: number,
    cachedInfo: MapInfo | null,
    enabled: Set<string>,
    skipInfoZoom: number = SKIP_INFO_ZOOM,
): LoadStrategy {
    if (zoom < MIN_DATA_ZOOM) {
        return { kind: 'below-min-zoom' };
    }
    if (zoom >= skipInfoZoom) {
        return { kind: 'skip-info', decision: decideSkipInfo(enabled) };
    }
    if (cachedInfo) {
        return {
            kind: 'optimistic',
            decision: decideLayerRendering(cachedInfo, enabled),
            revalidate: true,
            cachedInfo,
        };
    }
    return { kind: 'gated' };
}

/**
 * True when two decisions would render differently.
 *
 * Used by the optimistic path: after revalidation returns a fresh /info,
 * we only re-run the (expensive) GeoJSON fetches if the new decision flips
 * a layer's visibility or the cluster mode. Identical decisions short-
 * circuit to a chip refresh.
 */
export function decisionsDiffer(a: RenderingDecision, b: RenderingDecision): boolean {
    if (a.clusterMode !== b.clusterMode) return true;
    const aKeys = Object.keys(a.layers);
    const bKeys = Object.keys(b.layers);
    if (aKeys.length !== bKeys.length) return true;
    for (const key of aKeys) {
        if (a.layers[key] !== b.layers[key]) return true;
    }
    return false;
}

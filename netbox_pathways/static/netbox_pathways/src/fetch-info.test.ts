/**
 * Tests for `fetchMapInfo`'s callback contract.
 *
 * Callers need to distinguish "new info" (200 response, may change render
 * decision) from "unchanged" (304 Not Modified, cached info is still valid)
 * so they can avoid a needless re-render. The flag must be carried on the
 * callback so the cost of revalidation drops to a single round-trip plus
 * no DOM churn when nothing changed -- which is the common case during a
 * gentle pan.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchMapInfo, _resetInfoCache } from './data-layers';
import type { MapInfo } from './data-layers';

function makeInfoResponse(): MapInfo {
    return {
        bbox: null,
        counts: {
            structures: 50,
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
    };
}

describe('fetchMapInfo signals changed vs unchanged', () => {
    let fetchSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
        _resetInfoCache();
        fetchSpy = vi.spyOn(globalThis, 'fetch');
    });

    afterEach(() => {
        fetchSpy.mockRestore();
    });

    it('calls callback with changed=true on a 200 response with fresh data', async () => {
        const body = makeInfoResponse();
        fetchSpy.mockResolvedValueOnce(
            new Response(JSON.stringify(body), {
                status: 200,
                headers: { 'Content-Type': 'application/json', ETag: '"abc"' },
            }),
        );
        const cb = vi.fn();
        await fetchMapInfo('1,2,3,4', cb);
        expect(cb).toHaveBeenCalledTimes(1);
        const [info, changed] = cb.mock.calls[0];
        expect(changed).toBe(true);
        expect(info.counts.structures).toBe(50);
    });

    it('calls callback with changed=false on a 304 response, using cached info', async () => {
        // First call: 200 populates the cache.
        fetchSpy.mockResolvedValueOnce(
            new Response(JSON.stringify(makeInfoResponse()), {
                status: 200,
                headers: { 'Content-Type': 'application/json', ETag: '"abc"' },
            }),
        );
        await fetchMapInfo('1,2,3,4', vi.fn());

        // Second call: 304 must reuse the cached MapInfo and signal unchanged.
        fetchSpy.mockResolvedValueOnce(new Response(null, { status: 304 }));
        const cb = vi.fn();
        await fetchMapInfo('1,2,3,4', cb);
        expect(cb).toHaveBeenCalledTimes(1);
        const [info, changed] = cb.mock.calls[0];
        expect(changed).toBe(false);
        expect(info.counts.structures).toBe(50);
    });

    it('sends If-None-Match on the second call so 304 is reachable', async () => {
        fetchSpy.mockResolvedValueOnce(
            new Response(JSON.stringify(makeInfoResponse()), {
                status: 200,
                headers: { 'Content-Type': 'application/json', ETag: '"abc"' },
            }),
        );
        await fetchMapInfo('1,2,3,4', vi.fn());

        fetchSpy.mockResolvedValueOnce(new Response(null, { status: 304 }));
        await fetchMapInfo('1,2,3,4', vi.fn());

        const [, init] = fetchSpy.mock.calls[1];
        const headers = (init as RequestInit | undefined)?.headers as Record<string, string> | undefined;
        expect(headers && headers['If-None-Match']).toBe('"abc"');
    });
});

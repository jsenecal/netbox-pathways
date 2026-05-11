/**
 * Geometry state-machine operations for the map widget's helper buttons.
 *
 * computeAppendVertex decides what to do when a single [lon, lat] point is
 * fed into a LineString widget via "Use my location" or "Paste lat/lon...":
 *   - existing LineString -> append the point as a new vertex
 *   - pending point exists (no line yet) -> materialize a 2-vertex line
 *   - no line and no pending -> stash this point as pending
 *
 * The function is pure: callers are responsible for committing the geometry
 * to the hidden input and redrawing the map layer. See issue #32.
 */

export type AppendResult =
    | { kind: 'extended'; geometry: GeoJSON.LineString; pending: null }
    | { kind: 'started'; geometry: GeoJSON.LineString; pending: null }
    | { kind: 'pending'; geometry: null; pending: [number, number] };

export function computeAppendVertex(
    currentGeom: GeoJSON.Geometry | null,
    pending: [number, number] | null,
    newPoint: [number, number],
): AppendResult {
    if (currentGeom && currentGeom.type === 'LineString') {
        return {
            kind: 'extended',
            geometry: {
                type: 'LineString',
                coordinates: [...currentGeom.coordinates, newPoint],
            },
            pending: null,
        };
    }
    if (pending) {
        return {
            kind: 'started',
            geometry: { type: 'LineString', coordinates: [pending, newPoint] },
            pending: null,
        };
    }
    return { kind: 'pending', geometry: null, pending: newPoint };
}

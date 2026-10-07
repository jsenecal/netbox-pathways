/**
 * Polyline styling for the inline detail maps (initGeoMap).
 *
 * Kept free of Leaflet so it can be unit tested: callers pass the returned
 * object straight to L.polyline().
 */

export interface StyledLine {
    color?: string;
    /** Gap lines on the cable Map tab: drawn dashed. */
    dashed?: boolean;
    /** Stable id (e.g. "segment-12") that a highlight request matches. */
    key?: string;
}

export interface LineStyle {
    color: string;
    weight: number;
    opacity: number;
    dashArray?: string;
}

const WEIGHT = 4;
const OPACITY = 0.8;
const HIGHLIGHT_WEIGHT = 7;
const DIMMED_OPACITY = 0.25;

/** Style for `line`; with `highlight`, the matching line stands out and the rest dim. */
export function lineStyle(line: StyledLine, highlight?: string | null): LineStyle {
    const style: LineStyle = { color: line.color || 'blue', weight: WEIGHT, opacity: OPACITY };
    if (line.dashed) style.dashArray = '8 6';
    if (highlight) {
        if (line.key === highlight) {
            style.weight = HIGHLIGHT_WEIGHT;
            style.opacity = 1;
        } else {
            style.opacity = DIMMED_OPACITY;
        }
    }
    return style;
}

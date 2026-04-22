/**
 * Pure utility functions and constants extracted from pathways-map.ts.
 *
 * These are used by pathways-map, sidebar, popover, and tests.
 */

// ---------------------------------------------------------------------------
// Color & Icon Maps
// ---------------------------------------------------------------------------

export const STRUCTURE_COLORS: Record<string, string> = {
    'pole': '#2e7d32', 'manhole': '#1565c0', 'handhole': '#00838f',
    'cabinet': '#e65100', 'vault': '#6a1b9a', 'pedestal': '#f9a825',
    'building_entrance': '#c62828', 'splice_closure': '#795548',
    'tower': '#b71c1c', 'roof': '#616161', 'equipment_room': '#00796b',
    'telecom_closet': '#283593', 'riser_room': '#ad1457',
};

export const STRUCTURE_SHAPES: Record<string, string> = {
    'pole':               '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/><circle cx="10" cy="10" r="2.5"/>',
    'manhole':            '<circle cx="10" cy="10" r="8"/>',
    'handhole':           '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/>',
    'cabinet':            '<rect x="2" y="2" width="16" height="16" rx="4"/>',
    'vault':              '<rect x="2" y="2" width="16" height="16" rx="2"/>',
    'pedestal':           '<rect x="3" y="3" width="14" height="14" rx="2" fill="none" stroke-width="2.5"/>',
    'building_entrance':  '<rect x="3" y="3" width="14" height="14" rx="2" fill="none" stroke-width="2.5"/><circle cx="10" cy="10" r="2.5"/>',
    'splice_closure':     '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/><circle cx="10" cy="10" r="2.5"/>',
    'tower':              '<circle cx="10" cy="10" r="7" fill="none" stroke-width="2.5"/><line x1="10" y1="2" x2="10" y2="18" stroke-width="1.5"/><line x1="2" y1="10" x2="18" y2="10" stroke-width="1.5"/>',
    'roof':               '<polygon points="10,2 18,17 2,17"/>',
    'equipment_room':     '<rect x="3" y="3" width="14" height="14" rx="4" fill="none" stroke-width="2.5"/>',
    'telecom_closet':     '<rect x="3" y="3" width="10" height="10" rx="1" transform="rotate(45 10 10)"/>',
    'riser_room':         '<rect x="3.5" y="3.5" width="9" height="9" rx="1" fill="none" stroke-width="2.5" transform="rotate(45 10 10)"/>',
};

export const PATHWAY_COLORS: Record<string, string> = {
    'conduit': '#f57c00', 'conduit_bank': '#ad1457', 'aerial': '#1565c0',
    'direct_buried': '#616161', 'innerduct': '#e65100', 'microduct': '#6a1b9a',
    'tray': '#2e7d32', 'raceway': '#00838f', 'submarine': '#1a237e',
};

export const PATHWAY_DASH: Record<string, string> = {
    'conduit': '5,5', 'conduit_bank': '', 'aerial': '10,5',
    'direct_buried': '2,4', 'innerduct': '8,3', 'microduct': '1,3',
    'tray': '', 'raceway': '12,4', 'submarine': '6,2,2,2',
};

export interface PathwayStyleDef {
    color: string;
    weight: number;
    opacity: number;
    dashArray: string;
}

/** Return the polyline style for a given pathway_type key. */
export function pathwayStyle(pathwayType: string): PathwayStyleDef {
    const color = PATHWAY_COLORS[pathwayType] || '#888';
    const dash = PATHWAY_DASH[pathwayType] || '';
    const isBanks = pathwayType === 'conduit_bank';
    return {
        color,
        weight: isBanks ? 5 : 3,
        opacity: isBanks ? 0.8 : 0.7,
        dashArray: dash,
    };
}

// ---------------------------------------------------------------------------
// Marker helpers
// ---------------------------------------------------------------------------

export function structureIcon(type: string, size = 20): L.DivIcon {
    const color = STRUCTURE_COLORS[type] || '#616161';
    const shape = STRUCTURE_SHAPES[type] || '<circle cx="10" cy="10" r="8"/>';
    const isOutline = shape.includes('fill="none"');
    const half = size / 2;
    return L.divIcon({
        className: 'pw-marker',
        html: '<svg class="pw-marker-svg" viewBox="0 0 20 20" width="' + size +
              '" height="' + size + '" stroke="' + (isOutline ? color : 'white') +
              '" fill="' + color + '">' + shape + '</svg>',
        iconSize: [size, size] as [number, number],
        iconAnchor: [half, half] as [number, number],
        popupAnchor: [0, -(half + 2)] as [number, number],
    });
}

export function clusterIcon(count: number): L.DivIcon {
    let cls: string;
    let size: number;
    if (count < 10) {
        cls = 'pw-cluster-small'; size = 34;
    } else if (count < 100) {
        cls = 'pw-cluster-medium'; size = 40;
    } else {
        cls = 'pw-cluster-large'; size = 46;
    }
    return L.divIcon({
        className: 'pw-server-cluster',
        html: '<div class="pw-cluster-ring ' + cls + '" style="width:' + size +
              'px;height:' + size + 'px"><div class="pw-cluster-inner"><span>' +
              count + '</span></div></div>',
        iconSize: [size, size] as [number, number],
        iconAnchor: [size / 2, size / 2] as [number, number],
    });
}

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

export function esc(text: string): string {
    const el = document.createElement('span');
    el.textContent = text;
    return el.innerHTML;
}

export function titleCase(str: string): string {
    return (str || '').replace(/_/g, ' ').replace(/\b\w/g, function (c: string) { return c.toUpperCase(); });
}

export function getCookie(name: string): string | null {
    const value = '; ' + document.cookie;
    const parts = value.split('; ' + name + '=');
    if (parts.length === 2) return parts.pop()!.split(';').shift() || null;
    return null;
}

export function bboxParam(map: L.Map): string {
    const b = map.getBounds();
    return b.getWest() + ',' + b.getSouth() + ',' + b.getEast() + ',' + b.getNorth();
}

export function debounce(fn: () => void, delay: number): () => void {
    let timer: ReturnType<typeof setTimeout>;
    return function () {
        clearTimeout(timer);
        timer = setTimeout(fn, delay);
    };
}

export function haversine(lat1: number, lon1: number, lat2: number, lon2: number): number {
    const R = 6371000;
    const p1 = lat1 * Math.PI / 180;
    const p2 = lat2 * Math.PI / 180;
    const dp = (lat2 - lat1) * Math.PI / 180;
    const dl = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dp / 2) * Math.sin(dp / 2) +
              Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) * Math.sin(dl / 2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

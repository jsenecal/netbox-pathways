/**
 * Map core: map creation, base layers, overlays, and controls.
 *
 * Shared between the full-page infrastructure map (pathways-map.ts)
 * and the route planner map (route-planner-map.ts).
 */

import {
    STRUCTURE_COLORS,
    STRUCTURE_SHAPES,
    PATHWAY_COLORS,
    PATHWAY_DASH,
    createIconButtonControl,
    titleCase as _titleCase,
} from './map-utils';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const CFG: Partial<PathwaysConfig> = window.PATHWAYS_CONFIG || {};
const MAX_NATIVE_ZOOM: number = CFG.maxNativeZoom || 19;

// ---------------------------------------------------------------------------
// Base layers
// ---------------------------------------------------------------------------

interface BaseLayerDef {
    name: string;
    url: string;
    attribution?: string;
    maxNativeZoom?: number;
    tileSize?: number;
    zoomOffset?: number;
}

const DEFAULT_BASE_LAYERS: BaseLayerDef[] = [
    {
        name: 'Street',
        url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        attribution: '&copy; OpenStreetMap contributors',
        maxNativeZoom: MAX_NATIVE_ZOOM,
    },
    {
        name: 'Satellite',
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attribution: 'Esri World Imagery',
        maxNativeZoom: 19,
    },
];

export function createBaseLayers(): Record<string, L.TileLayer> {
    const configured = (CFG.baseLayers || []).filter(function (c: BaseLayerConfig) { return !!c.url; });
    const configs: BaseLayerDef[] = configured.length ? configured : DEFAULT_BASE_LAYERS;
    const layers: Record<string, L.TileLayer> = {};
    configs.forEach(function (cfg: BaseLayerDef) {
        layers[cfg.name] = L.tileLayer(cfg.url, {
            attribution: cfg.attribution || '',
            maxNativeZoom: cfg.maxNativeZoom || MAX_NATIVE_ZOOM,
            maxZoom: 22,
            tileSize: cfg.tileSize || 256,
            zoomOffset: cfg.zoomOffset || 0,
        });
    });
    return layers;
}

// ---------------------------------------------------------------------------
// User-configured overlays
// ---------------------------------------------------------------------------

export function createUserOverlays(): Record<string, L.TileLayer | L.TileLayer.WMS> {
    const userOverlays = CFG.overlays || [];
    const overlays: Record<string, L.TileLayer | L.TileLayer.WMS> = {};
    userOverlays.forEach(function (cfg: OverlayConfig) {
        let layer: L.TileLayer | L.TileLayer.WMS;
        if (cfg.type === 'wms') {
            layer = L.tileLayer.wms(cfg.url, {
                layers: (cfg['layers'] as string) || '',
                format: (cfg['format'] as string) || 'image/png',
                transparent: cfg['transparent'] !== false,
                attribution: (cfg['attribution'] as string) || '',
                maxZoom: 22,
            });
        } else {
            layer = L.tileLayer(cfg.url, {
                attribution: (cfg['attribution'] as string) || '',
                maxZoom: (cfg['maxZoom'] as number) || 22,
                maxNativeZoom: (cfg['maxNativeZoom'] as number) || undefined,
            });
        }
        overlays[cfg.name] = layer;
    });
    return overlays;
}

// ---------------------------------------------------------------------------
// Zoom hint overlay
// ---------------------------------------------------------------------------

export function createZoomHint(map: L.Map): HTMLDivElement {
    const div = L.DomUtil.create('div', 'pathways-zoom-hint') as HTMLDivElement;
    div.style.cssText =
        'position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);' +
        'z-index:800;padding:12px 24px;border-radius:8px;font-size:14px;' +
        'pointer-events:none;text-align:center;' +
        'background:rgba(0,0,0,0.7);color:#fff;';
    div.textContent = 'Zoom in to see infrastructure data';
    map.getContainer().appendChild(div);
    return div;
}

// ---------------------------------------------------------------------------
// Legend control
// ---------------------------------------------------------------------------

/**
 * Inject trusted static SVG markup into an element.
 *
 * Security: All SVG strings passed to this helper originate from compile-time
 * constants (STRUCTURE_SHAPES, PATHWAY_COLORS, PATHWAY_DASH) defined in this
 * file -- no user/network input is involved. This is the same trust model as
 * structureIcon() which also builds innerHTML from these constants.
 */
function _setStaticSvg(el: HTMLElement, svg: string): void {
    el.innerHTML = svg; // eslint-disable-line no-unsanitized/property -- trusted compile-time SVG constants only
}

export function createLegend(map: L.Map): void {
    const LegendControl = L.Control.extend({
        options: { position: 'bottomleft' },
        onAdd: function () {
            const container = L.DomUtil.create('div', 'pw-legend leaflet-bar');
            L.DomEvent.disableClickPropagation(container);
            L.DomEvent.disableScrollPropagation(container);

            // Header -- collapsed by default
            const header = L.DomUtil.create('div', 'pw-legend-header collapsed', container);
            const chevron = document.createElement('i');
            chevron.className = 'mdi mdi-chevron-down';
            header.appendChild(chevron);
            const titleSpan = document.createElement('span');
            titleSpan.textContent = 'Legend';
            header.appendChild(titleSpan);

            // Body -- collapsed by default
            const body = L.DomUtil.create('div', 'pw-legend-body collapsed', container);

            // Structures section
            const structSec = L.DomUtil.create('div', 'pw-legend-section', body);
            const structTitle = L.DomUtil.create('div', 'pw-legend-section-title', structSec);
            structTitle.textContent = 'Structures';

            const structTypes = ['pole', 'manhole', 'handhole', 'cabinet', 'vault',
                'pedestal', 'building_entrance', 'tower',
                'equipment_room', 'telecom_closet', 'riser_room'];
            for (let i = 0; i < structTypes.length; i++) {
                const stype = structTypes[i];
                const color = STRUCTURE_COLORS[stype] || '#616161';
                const shape = STRUCTURE_SHAPES[stype] || '<circle cx="10" cy="10" r="8"/>';
                const isOutline = shape.includes('fill="none"');
                const item = L.DomUtil.create('div', 'pw-legend-item', structSec);
                const swatch = L.DomUtil.create('span', 'pw-legend-swatch', item);
                _setStaticSvg(swatch,
                    '<svg viewBox="0 0 20 20" width="14" height="14" ' +
                    'stroke="' + (isOutline ? color : 'white') + '" fill="' + color + '">' +
                    shape + '</svg>');
                const label = L.DomUtil.create('span', 'pw-legend-label', item);
                label.textContent = _titleCase(stype);
            }

            // Pathways section
            const pathSec = L.DomUtil.create('div', 'pw-legend-section', body);
            const pathTitle = L.DomUtil.create('div', 'pw-legend-section-title', pathSec);
            pathTitle.textContent = 'Pathways';

            const pathTypes = ['conduit', 'conduit_bank', 'aerial', 'direct_buried',
                'innerduct', 'microduct', 'tray', 'raceway', 'submarine'];
            for (let i = 0; i < pathTypes.length; i++) {
                const ptype = pathTypes[i];
                const color = PATHWAY_COLORS[ptype] || '#616161';
                const dash = PATHWAY_DASH[ptype] || '';
                const item = L.DomUtil.create('div', 'pw-legend-item', pathSec);
                const swatch = L.DomUtil.create('span', 'pw-legend-swatch', item);
                _setStaticSvg(swatch,
                    '<svg viewBox="0 0 24 6" width="20" height="6">' +
                    '<line x1="0" y1="3" x2="24" y2="3" stroke="' + color +
                    '" stroke-width="3"' + (dash ? ' stroke-dasharray="' + dash + '"' : '') +
                    '/></svg>');
                const label = L.DomUtil.create('span', 'pw-legend-label', item);
                label.textContent = _titleCase(ptype);
            }

            // Toggle collapse
            header.addEventListener('click', function () {
                const isCollapsed = body.classList.toggle('collapsed');
                header.classList.toggle('collapsed', isCollapsed);
            });

            return container;
        },
    });

    new LegendControl().addTo(map);
}

// ---------------------------------------------------------------------------
// Stats control
// ---------------------------------------------------------------------------

export function createStatsControl(map: L.Map): void {
    const StatsControl = L.Control.extend({
        options: { position: 'bottomleft' },
        onAdd: function (): HTMLElement {
            const container = L.DomUtil.create('div', 'pw-stats-overlay');
            const sc = L.DomUtil.create('span', '', container);
            sc.id = 'structure-count';
            sc.textContent = '0';
            container.appendChild(document.createTextNode(' structures \u00b7 '));
            const pc = L.DomUtil.create('span', '', container);
            pc.id = 'pathway-count';
            pc.textContent = '0';
            container.appendChild(document.createTextNode(' pathways \u00b7 '));
            const tl = L.DomUtil.create('span', '', container);
            tl.id = 'total-length';
            tl.textContent = '0';
            container.appendChild(document.createTextNode(' km'));
            return container;
        },
    });
    new StatsControl().addTo(map);
}

// ---------------------------------------------------------------------------
// Locate control
// ---------------------------------------------------------------------------

export function createLocateControl(map: L.Map): L.Control {
    return createIconButtonControl({
        icon: 'mdi-crosshairs-gps',
        title: 'Go to my location',
        onClick: function () {
            if (!navigator.geolocation) return;
            navigator.geolocation.getCurrentPosition(
                function (pos: GeolocationPosition) {
                    map.flyTo([pos.coords.latitude, pos.coords.longitude], 17, { duration: 1 });
                },
                function () { /* silently ignore denial */ },
                { enableHighAccuracy: true, timeout: 10000 },
            );
        },
    });
}

// ---------------------------------------------------------------------------
// Kiosk control
// ---------------------------------------------------------------------------

/**
 * Enter or leave kiosk mode on the full-page map.
 *
 * Unlike the edit widget's maximize toggle, this is a navigation: kiosk state
 * lives in the URL so the view can render the page without the navbar and
 * breadcrumbs, and so a kiosk view stays shareable. The current position rides
 * along in the query string to survive the reload.
 */
export function createKioskControl(map: L.Map, isKiosk: boolean): L.Control {
    return createIconButtonControl({
        icon: isKiosk ? 'mdi-fullscreen-exit' : 'mdi-fullscreen',
        title: isKiosk ? 'Exit kiosk mode' : 'Kiosk mode',
        onClick: function () {
            const center = map.getCenter();
            const params = new URLSearchParams();
            params.set('lat', center.lat.toFixed(6));
            params.set('lon', center.lng.toFixed(6));
            params.set('zoom', String(map.getZoom()));
            if (!isKiosk) {
                params.set('kiosk', 'true');
            }
            window.location.search = params.toString();
        },
    });
}

// ---------------------------------------------------------------------------
// Sidebar toggle control
// ---------------------------------------------------------------------------

export function createSidebarToggleControl(isKiosk: boolean, showCallback: () => void): L.Control {
    // Kiosk mode slides the sidebar in over the map; docked mode hides it
    // out of the flex row. Opposite classes, same question.
    function sidebarVisible(sidebar: HTMLElement): boolean {
        return isKiosk
            ? sidebar.classList.contains('pw-sidebar-open')
            : !sidebar.classList.contains('pw-sidebar-hidden');
    }

    return createIconButtonControl({
        icon: 'mdi-chevron-left',
        title: 'Show sidebar',
        position: 'topright',
        className: 'pw-sidebar-toggle-ctrl',
        onClick: showCallback,
        onReady: function (container: HTMLElement) {
            // The button is redundant while the sidebar is on screen, so it
            // tracks the sidebar's class instead of being toggled by hand
            // from each of the several places that open or close it.
            function sync(): void {
                const sidebar = document.getElementById('pw-sidebar');
                if (!sidebar) return;
                container.style.display = sidebarVisible(sidebar) ? 'none' : '';
            }
            const sidebar = document.getElementById('pw-sidebar');
            if (!sidebar) return;
            new MutationObserver(sync).observe(sidebar, {
                attributes: true,
                attributeFilter: ['class'],
            });
            sync();
        },
    });
}

// ---------------------------------------------------------------------------
// Map factory
// ---------------------------------------------------------------------------

export interface MapInitConfig {
    center?: [number, number];
    zoom?: number;
    bounds?: L.LatLngBoundsExpression;
    kiosk?: boolean;
    select?: string;  // feature ID to auto-select, e.g. "structure-123"
    routeData?: unknown;  // Pre-loaded route geometry for static route display
}

export interface MapInstance {
    map: L.Map;
    baseLayers: Record<string, L.TileLayer>;
    layerControl: L.Control.Layers;
}

export function createMap(elementId: string, config: MapInitConfig): MapInstance {
    const baseLayers = createBaseLayers();
    const firstLayer = baseLayers[Object.keys(baseLayers)[0]];
    const map = L.map(elementId, {
        layers: [firstLayer],
    });

    // Fit to bounds if provided, otherwise use center/zoom
    if (config.bounds) {
        // Allow higher zoom when selecting a specific feature vs. viewing full data extent
        const boundsMaxZoom = config.select ? 20 : 17;
        map.fitBounds(config.bounds, { padding: [50, 50] as [number, number], maxZoom: boundsMaxZoom });
    } else {
        map.setView(config.center || [0, 0], config.zoom || 2);
    }

    // Overlay layers
    const overlayLayers: Record<string, L.Layer> = {};

    // User-configured WMS/WMTS/tile overlays
    const userOverlays = createUserOverlays();
    for (const name in userOverlays) {
        overlayLayers[name] = userOverlays[name];
    }

    // Layer control
    const layerControl = L.control.layers(baseLayers, overlayLayers, {
        position: 'bottomright', collapsed: true,
    }).addTo(map);

    return { map, baseLayers, layerControl };
}

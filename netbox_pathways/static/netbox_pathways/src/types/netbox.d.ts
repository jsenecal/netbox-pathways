/** Globals provided by NetBox and our plugin templates. */

declare global {
  interface PathwaysConfig {
    apiBase: string;
    maxNativeZoom: number;
    center?: [number, number];
    zoom?: number;
    minZoom?: number;
    maxZoom?: number;
    /**
     * Zoom at or above which the map skips `/info` and renders every
     * enabled layer immediately. Defaults to 17 in the client; overridable
     * via `PLUGINS_CONFIG['netbox_pathways']['map_skip_info_zoom']`.
     */
    skipInfoZoom?: number;
    /** Zoom-out floor for the edit widget map (default 14 in the client). */
    widgetMinZoom?: number;
    /**
     * Zoom at or above which structures with an area geometry draw their real
     * footprint instead of a single icon marker. Defaults to 18 in the client;
     * overridable via
     * `PLUGINS_CONFIG['netbox_pathways']['map_structure_polygon_zoom']`.
     */
    structurePolygonZoom?: number;
    overlays?: OverlayConfig[];
    baseLayers?: BaseLayerConfig[];
    externalLayers?: import('./external').ExternalLayerConfig[];
    /** Available lifecycle status choices for the hide-inactive panel. */
    statuses?: import('../status-prefs').StatusChoice[];
  }

  interface OverlayConfig {
    name: string;
    type: 'wms' | 'wmts' | 'tile';
    url: string;
    [key: string]: unknown;
  }

  interface BaseLayerConfig {
    name: string;
    url: string;
    tileSize?: number;
    zoomOffset?: number;
    attribution?: string;
    maxNativeZoom?: number;
    [key: string]: unknown;
  }

  interface Window {
    PATHWAYS_CONFIG?: PathwaysConfig;
    initializePathwaysMap?: (mapId: string, config: Record<string, unknown>) => void;
    initializeRoutePlannerMap?: (mapId: string, config: Record<string, unknown>) => void;
    _rpMap?: L.Map;
    _rpRouteLayer?: L.FeatureGroup | null;
    _rpMarkerLayer?: L.FeatureGroup | null;
    /** Map helpers the route planner templates reach for inline. */
    pwStructureIcon?: typeof import('../map-utils').structureIcon;
    pwPathwayStyle?: typeof import('../map-utils').pathwayStyle;
    pwPopover?: typeof import('../popover').Popover;
    pwTitleCase?: typeof import('../map-utils').titleCase;
  }
}

export {};

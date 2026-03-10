/** Globals provided by NetBox and our plugin templates. */

interface PathwaysConfig {
  apiBase: string;
  maxNativeZoom: number;
  overlays?: OverlayConfig[];
  baseLayers?: BaseLayerConfig[];
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

declare global {
  interface Window {
    PATHWAYS_CONFIG?: PathwaysConfig;
    initializePathwaysMap?: (mapId: string, config: Record<string, unknown>) => void;
  }
}

export {};

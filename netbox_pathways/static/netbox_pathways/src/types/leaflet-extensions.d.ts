/** Type augmentations for Leaflet plugins and django-leaflet. */

import * as L from 'leaflet';
import 'leaflet.markercluster';

declare module 'leaflet' {
  interface MarkerOptions {
    _origIcon?: L.Icon | L.DivIcon;
  }

  interface PathOptions {
    _origStyle?: L.PathOptions;
  }
}

declare global {
  /** The global Leaflet namespace, loaded via <script> tag. */
  // eslint-disable-next-line no-var
  var L: typeof import('leaflet');

  /**
   * The L namespace re-exported so that `L.Map`, `L.Layer`, etc. resolve
   * in type position across non-module scripts.
   */
  namespace L {
    export type Map = import('leaflet').Map;
    export type Layer = import('leaflet').Layer;
    export type LatLng = import('leaflet').LatLng;
    export type LatLngBounds = import('leaflet').LatLngBounds;
    export type LayerGroup = import('leaflet').LayerGroup;
    export type Icon = import('leaflet').Icon;
    export type DivIcon = import('leaflet').DivIcon;
    export type Marker = import('leaflet').Marker;
    export type Polyline = import('leaflet').Polyline;
    export type TileLayer = import('leaflet').TileLayer;
    export type GeoJSON = import('leaflet').GeoJSON;
    export type PathOptions = import('leaflet').PathOptions;
    export type TileLayerOptions = import('leaflet').TileLayerOptions;
    export type ControlOptions = import('leaflet').ControlOptions;
    export type LayersControlEvent = import('leaflet').LayersControlEvent;
    export type Control = import('leaflet').Control;
    export type LeafletMouseEvent = import('leaflet').LeafletMouseEvent;
    export type LeafletEvent = import('leaflet').LeafletEvent;
    export type LatLngBoundsExpression = import('leaflet').LatLngBoundsExpression;
    export type GeoJSONOptions = import('leaflet').GeoJSONOptions;
    export type CircleMarker = import('leaflet').CircleMarker;
    export type CircleMarkerOptions = import('leaflet').CircleMarkerOptions;
    export type Polygon = import('leaflet').Polygon;
    export type LatLngExpression = import('leaflet').LatLngExpression;
    // Nested namespace for L.Control.Layers and L.TileLayer.WMS
    export namespace Control {
      export type Layers = import('leaflet').Control.Layers;
    }
    export namespace TileLayer {
      export type WMS = import('leaflet').TileLayer.WMS;
    }
  }

  /** Custom event fired by django-leaflet on map widget initialization. */
  interface MapInitEvent extends CustomEvent {
    detail: {
      map: L.Map;
    };
  }
}

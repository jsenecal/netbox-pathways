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
    export type LayerGroup = import('leaflet').LayerGroup;
    export type Icon = import('leaflet').Icon;
    export type DivIcon = import('leaflet').DivIcon;
    export type PathOptions = import('leaflet').PathOptions;
    export type Control = import('leaflet').Control;
  }

  /** Custom event fired by django-leaflet on map widget initialization. */
  interface MapInitEvent extends CustomEvent {
    detail: {
      map: L.Map;
    };
  }
}

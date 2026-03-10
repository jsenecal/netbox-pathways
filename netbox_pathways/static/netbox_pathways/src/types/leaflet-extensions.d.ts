/** Type augmentations for Leaflet plugins and django-leaflet. */

import 'leaflet';
import 'leaflet.markercluster';

declare module 'leaflet' {
  interface MarkerOptions {
    _origIcon?: L.Icon | L.DivIcon;
  }

  interface PathOptions {
    _origStyle?: L.PathOptions;
  }
}

interface MapInitEvent extends CustomEvent {
  detail: {
    map: L.Map;
  };
}

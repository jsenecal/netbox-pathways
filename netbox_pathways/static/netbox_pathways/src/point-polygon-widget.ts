/**
 * Disable the polyline draw tool on PointPolygonWidget maps.
 *
 * django-leaflet fires a 'map:init' event per widget. We intercept it
 * and remove the polyline button from any draw control on that map.
 */

(function () {
  'use strict';

  document.addEventListener('map:init', function (e: Event) {
    const customEvent = e as MapInitEvent;
    const map: L.Map | undefined =
      customEvent.detail?.map ||
      ((e as Record<string, any>).originalEvent?.detail?.map as L.Map | undefined);
    if (!map) return;

    // The draw control is stored on the map by django-leaflet
    const mapRecord = map as Record<string, any>;
    for (const key in mapRecord) {
      if (key.indexOf('drawControl') === 0 && mapRecord[key] && mapRecord[key]._toolbars) {
        const drawToolbar = mapRecord[key]._toolbars.draw;
        if (drawToolbar?._modes?.polyline) {
          // Remove the polyline handler button
          const btn: HTMLElement | undefined = drawToolbar._modes.polyline.button;
          if (btn?.parentNode) {
            btn.parentNode.removeChild(btn);
          }
        }
      }
    }
  });
})();

/**
 * Fix Leaflet.Draw edit/delete toolbar buttons staying disabled after
 * existing geometry is loaded from the form field.
 *
 * The root cause is a timing issue in django-leaflet + Leaflet.Draw:
 * the edit toolbar calls _checkDisabled() when the featureGroup is still
 * empty, and the subsequent layeradd event doesn't always re-enable the
 * buttons reliably.  We hook into the map:loadfield event (fired after
 * geometry is deserialized and added) and explicitly re-run _checkDisabled.
 */

interface MapInitDetail {
  map: L.Map & Record<string, any>;
}

interface LoadFieldEvent {
  field: {
    _drawControl?: {
      _toolbars?: Record<
        string,
        { _checkDisabled?: () => void }
      >;
    };
  };
}

(function () {
  'use strict';

  window.addEventListener('map:init', function (e: Event) {
    const detail = (e as CustomEvent<MapInitDetail>).detail;
    const map = detail?.map;
    if (!map) return;

    map.on('map:loadfield', function (evt: unknown) {
      const loadEvt = evt as LoadFieldEvent;
      const drawControl = loadEvt.field?._drawControl;
      if (!drawControl?._toolbars) return;

      for (const key in drawControl._toolbars) {
        const toolbar = drawControl._toolbars[key];
        if (typeof toolbar._checkDisabled === 'function') {
          toolbar._checkDisabled();
        }
      }
    });
  });
})();

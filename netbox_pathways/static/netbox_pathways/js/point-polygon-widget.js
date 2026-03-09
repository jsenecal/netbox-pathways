/**
 * Disable the polyline draw tool on PointPolygonWidget maps.
 *
 * django-leaflet fires a 'map:init' event per widget. We intercept it
 * and remove the polyline button from any draw control on that map.
 */
(function() {
    'use strict';

    document.addEventListener('map:init', function(e) {
        var map = e.detail.map || (e.originalEvent && e.originalEvent.detail && e.originalEvent.detail.map);
        if (!map) return;

        // Find draw controls on this map and disable polyline
        map.eachLayer(function(layer) {
            if (layer instanceof L.Control.Draw) {
                // Not reachable via eachLayer — controls aren't layers
            }
        });

        // The draw control is stored on the map by django-leaflet
        for (var key in map) {
            if (key.indexOf('drawControl') === 0 && map[key] && map[key]._toolbars) {
                var drawToolbar = map[key]._toolbars.draw;
                if (drawToolbar && drawToolbar._modes && drawToolbar._modes.polyline) {
                    // Remove the polyline handler button
                    var btn = drawToolbar._modes.polyline.button;
                    if (btn && btn.parentNode) {
                        btn.parentNode.removeChild(btn);
                    }
                }
            }
        }
    });
})();

/**
 * Reusable Leaflet map for detail pages.
 *
 * Data format:
 * {
 *   points: [{ lat, lon, name, color, url }],
 *   lines:  [{ coords: [[lon,lat],...], name, color, url }]
 * }
 */

function _escapeHtml(text) {
    var el = document.createElement('span');
    el.textContent = text;
    return el.innerHTML;
}

function initGeoMap(containerId, data) {
    var container = document.getElementById(containerId);
    if (!container || container._leafletMap) return container._leafletMap;

    var map = L.map(containerId, { scrollWheelZoom: true });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);

    var bounds = L.latLngBounds();

    if (data.points) {
        data.points.forEach(function(pt) {
            var marker = L.circleMarker([pt.lat, pt.lon], {
                radius: 8,
                fillColor: pt.color || 'blue',
                color: '#000',
                weight: 1,
                opacity: 1,
                fillOpacity: 0.8
            }).addTo(map);

            var html = '<strong>' + _escapeHtml(pt.name) + '</strong>';
            if (pt.url) {
                html += '<br><a href="' + _escapeHtml(pt.url) + '" class="btn btn-sm btn-primary mt-1">View</a>';
            }
            marker.bindPopup(html);
            bounds.extend([pt.lat, pt.lon]);
        });
    }

    if (data.lines) {
        data.lines.forEach(function(line) {
            var latlngs = line.coords.map(function(c) { return [c[1], c[0]]; });
            var polyline = L.polyline(latlngs, {
                color: line.color || 'blue',
                weight: 4,
                opacity: 0.8
            }).addTo(map);

            var html = '<strong>' + _escapeHtml(line.name) + '</strong>';
            if (line.url) {
                html += '<br><a href="' + _escapeHtml(line.url) + '" class="btn btn-sm btn-primary mt-1">View</a>';
            }
            polyline.bindPopup(html);

            latlngs.forEach(function(ll) { bounds.extend(ll); });
        });
    }

    if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 17 });
    } else {
        map.setView([0, 0], 2);
    }

    container._leafletMap = map;
    return map;
}

let map;
let structuresLayer;
let pathwaysLayer;
let structuresVisible = true;
let pathwaysVisible = true;

function _esc(text) {
    var el = document.createElement('span');
    el.textContent = text;
    return el.innerHTML;
}

const structureColors = {
    'Pole': 'green',
    'Manhole': 'blue',
    'Handhole': 'cyan',
    'Cabinet': 'orange',
    'Vault': 'purple',
    'Pedestal': 'yellow',
    'Building Entrance': 'red',
    'Splice Closure': 'brown',
    'Tower': 'darkred',
    'Rooftop': 'gray',
    'Equipment Room': 'teal',
    'Telecom Closet': 'indigo',
    'Riser Room': 'pink',
    'Unknown': 'gray'
};

const pathwayColors = {
    'Conduit': 'brown',
    'Aerial Span': 'blue',
    'Direct Buried': 'gray',
    'Innerduct': 'orange',
    'Microduct': 'purple',
    'Cable Tray': 'green',
    'Raceway': 'cyan',
    'Submarine': 'navy'
};

function initializePathwaysMap(elementId, config) {
    map = L.map(elementId).setView(config.center, config.zoom);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);

    structuresLayer = L.layerGroup().addTo(map);
    pathwaysLayer = L.layerGroup().addTo(map);

    if (config.structures && config.structures.length > 0) {
        addStructuresToMap(config.structures);
        document.getElementById('structure-count').textContent = config.structures.length;
    }

    if (config.pathways && config.pathways.length > 0) {
        addPathwaysToMap(config.pathways);
        document.getElementById('pathway-count').textContent = config.pathways.length;
    }

    setupEventHandlers();
    calculateTotalLength(config.pathways);
}

function addStructuresToMap(structures) {
    structures.forEach(function(structure) {
        var coords = structure.geometry.coordinates;
        var color = structureColors[structure.properties.type] || 'gray';

        var marker = L.circleMarker([coords[1], coords[0]], {
            radius: 8,
            fillColor: color,
            color: '#000',
            weight: 1,
            opacity: 1,
            fillOpacity: 0.8
        });

        var popupContent =
            '<div class="pathways-popup">' +
            '<h5>' + _esc(structure.properties.name) + '</h5>' +
            '<table class="table table-sm">' +
            '<tr><td><strong>Type:</strong></td><td>' + _esc(structure.properties.type) + '</td></tr>' +
            '<tr><td><strong>Site:</strong></td><td>' + _esc(structure.properties.site) + '</td></tr>' +
            '</table>' +
            '<a href="' + _esc(structure.properties.url) + '" class="btn btn-sm btn-primary">View Details</a>' +
            '</div>';

        marker.bindPopup(popupContent);
        marker.addTo(structuresLayer);
    });
}

function addPathwaysToMap(pathways) {
    pathways.forEach(function(pathway) {
        var coords = pathway.geometry.coordinates;
        var color = pathwayColors[pathway.properties.pathway_type] || 'gray';

        var latlngs = coords.map(function(coord) { return [coord[1], coord[0]]; });

        var polyline = L.polyline(latlngs, {
            color: color,
            weight: 3,
            opacity: 0.7
        });

        var popupContent =
            '<div class="pathways-popup">' +
            '<h5>' + _esc(pathway.properties.name) + '</h5>' +
            '<table class="table table-sm">' +
            '<tr><td><strong>Type:</strong></td><td>' + _esc(pathway.properties.pathway_type) + '</td></tr>' +
            '<tr><td><strong>Cables:</strong></td><td>' + (pathway.properties.cables_routed || 0) + '</td></tr>' +
            '</table>' +
            '<a href="' + _esc(pathway.properties.url) + '" class="btn btn-sm btn-primary">View Details</a>' +
            '</div>';

        polyline.bindPopup(popupContent);
        polyline.addTo(pathwaysLayer);
    });
}

function setupEventHandlers() {
    document.getElementById('toggle-structures').addEventListener('click', function() {
        structuresVisible = !structuresVisible;
        if (structuresVisible) {
            map.addLayer(structuresLayer);
            this.classList.remove('btn-secondary');
            this.classList.add('btn-primary');
        } else {
            map.removeLayer(structuresLayer);
            this.classList.remove('btn-primary');
            this.classList.add('btn-secondary');
        }
    });

    document.getElementById('toggle-pathways').addEventListener('click', function() {
        pathwaysVisible = !pathwaysVisible;
        if (pathwaysVisible) {
            map.addLayer(pathwaysLayer);
            this.classList.remove('btn-secondary');
            this.classList.add('btn-primary');
        } else {
            map.removeLayer(pathwaysLayer);
            this.classList.remove('btn-primary');
            this.classList.add('btn-secondary');
        }
    });

    document.getElementById('reset-view').addEventListener('click', function() {
        var bounds = L.featureGroup([structuresLayer, pathwaysLayer]).getBounds();
        if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [50, 50] });
        }
    });
}

function calculateTotalLength(pathways) {
    if (!pathways || pathways.length === 0) {
        document.getElementById('total-length').textContent = '0';
        return;
    }

    var totalLength = 0;
    pathways.forEach(function(pathway) {
        var coords = pathway.geometry.coordinates;
        for (var i = 0; i < coords.length - 1; i++) {
            totalLength += haversineDistance(
                coords[i][1], coords[i][0],
                coords[i + 1][1], coords[i + 1][0]
            );
        }
    });

    document.getElementById('total-length').textContent = (totalLength / 1000).toFixed(2);
}

function haversineDistance(lat1, lon1, lat2, lon2) {
    var R = 6371000;
    var p1 = lat1 * Math.PI / 180;
    var p2 = lat2 * Math.PI / 180;
    var dp = (lat2 - lat1) * Math.PI / 180;
    var dl = (lon2 - lon1) * Math.PI / 180;

    var a = Math.sin(dp / 2) * Math.sin(dp / 2) +
            Math.cos(p1) * Math.cos(p2) *
            Math.sin(dl / 2) * Math.sin(dl / 2);
    var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    return R * c;
}

window.PathwaysMap = {
    initialize: initializePathwaysMap,
    addStructures: addStructuresToMap,
    addPathways: addPathwaysToMap,
    getMap: function() { return map; }
};

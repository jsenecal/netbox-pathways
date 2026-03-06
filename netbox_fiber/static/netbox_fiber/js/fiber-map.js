// Fiber Map JavaScript - Leaflet Integration

let map;
let structuresLayer;
let conduitsLayer;
let structuresVisible = true;
let conduitsVisible = true;

// Structure type colors
const structureColors = {
    'Pole': 'green',
    'Manhole': 'blue',
    'Handhole': 'cyan',
    'Cabinet': 'orange',
    'Vault': 'purple',
    'Pedestal': 'yellow',
    'Building Entrance': 'red',
    'Splice Closure': 'brown'
};

// Conduit type colors
const conduitColors = {
    'Underground': 'brown',
    'Aerial': 'blue',
    'Submarine': 'navy',
    'Direct Buried': 'gray',
    'Indoor': 'green'
};

function initializeFiberMap(elementId, config) {
    // Initialize the map
    map = L.map(elementId).setView(config.center, config.zoom);
    
    // Add OpenStreetMap tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);
    
    // Create layer groups
    structuresLayer = L.layerGroup().addTo(map);
    conduitsLayer = L.layerGroup().addTo(map);
    
    // Add structures to map
    if (config.structures && config.structures.length > 0) {
        addStructuresToMap(config.structures);
        document.getElementById('structure-count').textContent = config.structures.length;
    }
    
    // Add conduits to map
    if (config.conduits && config.conduits.length > 0) {
        addConduitsToMap(config.conduits);
        document.getElementById('conduit-count').textContent = config.conduits.length;
    }
    
    // Set up event handlers
    setupEventHandlers();
    
    // Calculate total conduit length
    calculateTotalLength(config.conduits);
}

function addStructuresToMap(structures) {
    structures.forEach(structure => {
        const coords = structure.geometry.coordinates;
        const color = structureColors[structure.properties.type] || 'gray';
        
        const marker = L.circleMarker([coords[1], coords[0]], {
            radius: 8,
            fillColor: color,
            color: '#000',
            weight: 1,
            opacity: 1,
            fillOpacity: 0.8
        });
        
        // Create popup content
        const popupContent = `
            <div class="fiber-popup">
                <h5>${structure.properties.name}</h5>
                <table class="table table-sm">
                    <tr><td><strong>Type:</strong></td><td>${structure.properties.type}</td></tr>
                    <tr><td><strong>Site:</strong></td><td>${structure.properties.site}</td></tr>
                </table>
                <a href="${structure.properties.url}" class="btn btn-sm btn-primary">View Details</a>
            </div>
        `;
        
        marker.bindPopup(popupContent);
        marker.addTo(structuresLayer);
    });
}

function addConduitsToMap(conduits) {
    conduits.forEach(conduit => {
        const coords = conduit.geometry.coordinates;
        const color = conduitColors[conduit.properties.type] || 'gray';
        
        // Convert coordinates for Leaflet (swap lat/lng)
        const latlngs = coords.map(coord => [coord[1], coord[0]]);
        
        const polyline = L.polyline(latlngs, {
            color: color,
            weight: 3,
            opacity: 0.7
        });
        
        // Create popup content
        const popupContent = `
            <div class="fiber-popup">
                <h5>${conduit.properties.name}</h5>
                <table class="table table-sm">
                    <tr><td><strong>Type:</strong></td><td>${conduit.properties.type}</td></tr>
                    <tr><td><strong>Utilization:</strong></td><td>${conduit.properties.utilization.toFixed(1)}%</td></tr>
                </table>
                <div class="progress mb-2">
                    <div class="progress-bar" role="progressbar" 
                         style="width: ${conduit.properties.utilization}%"
                         aria-valuenow="${conduit.properties.utilization}" 
                         aria-valuemin="0" aria-valuemax="100">
                    </div>
                </div>
                <a href="${conduit.properties.url}" class="btn btn-sm btn-primary">View Details</a>
            </div>
        `;
        
        polyline.bindPopup(popupContent);
        polyline.addTo(conduitsLayer);
    });
}

function setupEventHandlers() {
    // Toggle structures visibility
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
    
    // Toggle conduits visibility
    document.getElementById('toggle-conduits').addEventListener('click', function() {
        conduitsVisible = !conduitsVisible;
        if (conduitsVisible) {
            map.addLayer(conduitsLayer);
            this.classList.remove('btn-secondary');
            this.classList.add('btn-primary');
        } else {
            map.removeLayer(conduitsLayer);
            this.classList.remove('btn-primary');
            this.classList.add('btn-secondary');
        }
    });
    
    // Reset map view
    document.getElementById('reset-view').addEventListener('click', function() {
        const bounds = L.featureGroup([structuresLayer, conduitsLayer]).getBounds();
        if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [50, 50] });
        }
    });
}

function calculateTotalLength(conduits) {
    if (!conduits || conduits.length === 0) {
        document.getElementById('total-length').textContent = '0';
        return;
    }
    
    let totalLength = 0;
    conduits.forEach(conduit => {
        const coords = conduit.geometry.coordinates;
        for (let i = 0; i < coords.length - 1; i++) {
            const distance = calculateDistance(
                coords[i][1], coords[i][0],
                coords[i + 1][1], coords[i + 1][0]
            );
            totalLength += distance;
        }
    });
    
    // Convert to kilometers and display
    document.getElementById('total-length').textContent = (totalLength / 1000).toFixed(2);
}

function calculateDistance(lat1, lon1, lat2, lon2) {
    // Haversine formula for calculating distance between two points
    const R = 6371000; // Earth's radius in meters
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180;
    const Δφ = (lat2 - lat1) * Math.PI / 180;
    const Δλ = (lon2 - lon1) * Math.PI / 180;
    
    const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
              Math.cos(φ1) * Math.cos(φ2) *
              Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    
    return R * c; // Distance in meters
}

// Export functions for use in other scripts
window.FiberMap = {
    initialize: initializeFiberMap,
    addStructures: addStructuresToMap,
    addConduits: addConduitsToMap,
    getMap: () => map
};
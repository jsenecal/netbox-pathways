/**
 * Geoman draw mode configuration per geometry type.
 * Internal module — imported by pathways-field.ts, not a standalone entrypoint.
 */

interface GeomanControlOptions {
  position: string;
  drawMarker: boolean;
  drawCircleMarker: boolean;
  drawPolyline: boolean;
  drawRectangle: boolean;
  drawPolygon: boolean;
  drawCircle: boolean;
  drawText: boolean;
  editMode: boolean;
  dragMode: boolean;
  removalMode: boolean;
  cutPolygon: boolean;
  rotateMode: boolean;
}

const DEFAULTS: GeomanControlOptions = {
  position: 'topleft',
  drawMarker: false,
  drawCircleMarker: false,
  drawPolyline: false,
  drawRectangle: false,
  drawPolygon: false,
  drawCircle: false,
  drawText: false,
  editMode: true,
  dragMode: true,
  removalMode: true,
  cutPolygon: false,
  rotateMode: false,
};

/**
 * Returns geoman addControls options for a given geometry type.
 * geomType comes from OGRGeomType.name: "Line String", "Point", "Geometry", etc.
 */
export function getControlOptions(geomType: string): GeomanControlOptions {
  const normalized = geomType.replace(/\s+/g, '').toLowerCase();
  switch (normalized) {
    case 'linestring':
      return { ...DEFAULTS, drawPolyline: true };
    case 'point':
      return { ...DEFAULTS, drawMarker: true };
    case 'geometry':
      return { ...DEFAULTS, drawMarker: true, drawPolygon: true };
    default:
      return { ...DEFAULTS, drawPolyline: true };
  }
}

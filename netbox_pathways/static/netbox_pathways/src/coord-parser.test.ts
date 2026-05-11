/**
 * Tests for the coord-parser module.
 *
 * parseGeometryInput accepts forgiving free-text input and normalizes it to
 * a GeoJSON geometry. Supported formats:
 *   - GeoJSON Geometry  ({type, coordinates})
 *   - GeoJSON Feature   (unwraps .geometry)
 *   - WKT               (POINT, LINESTRING, POLYGON)
 *   - DMS               (45 30 15 N 73 34 00 W) for points only
 *
 * Bare "lat,lon" strings are intentionally NOT supported: the Map tab has a
 * dedicated "Paste lat/lon..." helper for that. See issue #32.
 */

import { describe, it, expect } from 'vitest';
import { parseGeometryInput } from './coord-parser';

describe('parseGeometryInput - empty input', () => {
    it('returns null geometry and no error for empty string', () => {
        const r = parseGeometryInput('', 'Point');
        expect(r.geometry).toBeNull();
        expect(r.error).toBeNull();
    });

    it('returns null geometry and no error for whitespace only', () => {
        const r = parseGeometryInput('   \n\t  ', 'LineString');
        expect(r.geometry).toBeNull();
        expect(r.error).toBeNull();
    });
});

describe('parseGeometryInput - GeoJSON Geometry', () => {
    it('passes a Point through', () => {
        const text = '{"type":"Point","coordinates":[-73.5,45.5]}';
        const r = parseGeometryInput(text, 'Point');
        expect(r.error).toBeNull();
        expect(r.geometry).toEqual({ type: 'Point', coordinates: [-73.5, 45.5] });
    });

    it('passes a LineString through', () => {
        const text = '{"type":"LineString","coordinates":[[-73.5,45.5],[-73.4,45.6]]}';
        const r = parseGeometryInput(text, 'LineString');
        expect(r.error).toBeNull();
        expect(r.geometry).toEqual({
            type: 'LineString',
            coordinates: [[-73.5, 45.5], [-73.4, 45.6]],
        });
    });

    it('tolerates pretty-printed JSON', () => {
        const text = `{
            "type": "Point",
            "coordinates": [-73.5, 45.5]
        }`;
        const r = parseGeometryInput(text, 'Point');
        expect(r.error).toBeNull();
        expect(r.geometry?.type).toBe('Point');
    });
});

describe('parseGeometryInput - GeoJSON Feature unwrap', () => {
    it('unwraps a Feature to its geometry', () => {
        const text = JSON.stringify({
            type: 'Feature',
            properties: { name: 'foo' },
            geometry: { type: 'Point', coordinates: [-73.5, 45.5] },
        });
        const r = parseGeometryInput(text, 'Point');
        expect(r.error).toBeNull();
        expect(r.geometry).toEqual({ type: 'Point', coordinates: [-73.5, 45.5] });
    });

    it('takes the first geometry from a FeatureCollection', () => {
        const text = JSON.stringify({
            type: 'FeatureCollection',
            features: [
                { type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: [-73.5, 45.5] } },
                { type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: [0, 0] } },
            ],
        });
        const r = parseGeometryInput(text, 'Point');
        expect(r.error).toBeNull();
        expect(r.geometry).toEqual({ type: 'Point', coordinates: [-73.5, 45.5] });
    });

    it('errors when a Feature has null geometry', () => {
        const text = JSON.stringify({ type: 'Feature', properties: {}, geometry: null });
        const r = parseGeometryInput(text, 'Point');
        expect(r.geometry).toBeNull();
        expect(r.error).toMatch(/no geometry/i);
    });
});

describe('parseGeometryInput - WKT', () => {
    it('parses POINT', () => {
        const r = parseGeometryInput('POINT(-73.5 45.5)', 'Point');
        expect(r.error).toBeNull();
        expect(r.geometry).toEqual({ type: 'Point', coordinates: [-73.5, 45.5] });
    });

    it('parses POINT with extra whitespace and lower case', () => {
        const r = parseGeometryInput('  point ( -73.5   45.5 )  ', 'Point');
        expect(r.error).toBeNull();
        expect(r.geometry).toEqual({ type: 'Point', coordinates: [-73.5, 45.5] });
    });

    it('parses LINESTRING', () => {
        const r = parseGeometryInput('LINESTRING(-73.5 45.5, -73.4 45.6, -73.3 45.7)', 'LineString');
        expect(r.error).toBeNull();
        expect(r.geometry).toEqual({
            type: 'LineString',
            coordinates: [[-73.5, 45.5], [-73.4, 45.6], [-73.3, 45.7]],
        });
    });

    it('rejects WKT with too few coordinate pairs for LINESTRING', () => {
        const r = parseGeometryInput('LINESTRING(-73.5 45.5)', 'LineString');
        expect(r.geometry).toBeNull();
        expect(r.error).toMatch(/at least two/i);
    });

    it('rejects malformed WKT', () => {
        const r = parseGeometryInput('POINT(foo bar)', 'Point');
        expect(r.geometry).toBeNull();
        expect(r.error).not.toBeNull();
    });
});

describe('parseGeometryInput - DMS', () => {
    it('parses a DMS pair with hemisphere letters', () => {
        const r = parseGeometryInput('45 30 15 N 73 34 00 W', 'Point');
        expect(r.error).toBeNull();
        expect(r.geometry?.type).toBe('Point');
        const coords = (r.geometry as GeoJSON.Point).coordinates;
        expect(coords[1]).toBeCloseTo(45.5041667, 4);
        expect(coords[0]).toBeCloseTo(-73.5666667, 4);
    });

    it('parses DMS with symbols and hemispheres', () => {
        const r = parseGeometryInput(`45°30'15"N 73°34'00"W`, 'Point');
        expect(r.error).toBeNull();
        const coords = (r.geometry as GeoJSON.Point).coordinates;
        expect(coords[1]).toBeCloseTo(45.5041667, 4);
        expect(coords[0]).toBeCloseTo(-73.5666667, 4);
    });

    it('parses DMS with comma separator between lat and lon', () => {
        const r = parseGeometryInput(`45°30'15"N, 73°34'00"W`, 'Point');
        expect(r.error).toBeNull();
        expect(r.geometry?.type).toBe('Point');
    });

    it('parses DMS without hemispheres, assuming lat,lon order', () => {
        // No N/S/E/W -- assume Google Maps convention (lat first).
        const r = parseGeometryInput('45 30 15 -73 34 00', 'Point');
        expect(r.error).toBeNull();
        expect(r.geometry?.type).toBe('Point');
        const coords = (r.geometry as GeoJSON.Point).coordinates;
        expect(coords[1]).toBeCloseTo(45.5041667, 4);
        expect(coords[0]).toBeCloseTo(-73.5666667, 4);
    });

    it('parses DMS-without-hemispheres with symbols', () => {
        const r = parseGeometryInput(`45°30'15" -73°34'00"`, 'Point');
        expect(r.error).toBeNull();
        const coords = (r.geometry as GeoJSON.Point).coordinates;
        expect(coords[1]).toBeCloseTo(45.5041667, 4);
        expect(coords[0]).toBeCloseTo(-73.5666667, 4);
    });
});

describe('parseGeometryInput - bare decimal lat,lon (Google Maps style)', () => {
    it('parses "41.40338, 2.17403" as a Point [lon, lat]', () => {
        const r = parseGeometryInput('41.40338, 2.17403', 'Point');
        expect(r.error).toBeNull();
        expect(r.geometry).toEqual({ type: 'Point', coordinates: [2.17403, 41.40338] });
    });

    it('parses space-separated pair', () => {
        const r = parseGeometryInput('45.5 -73.5', 'Point');
        expect(r.error).toBeNull();
        expect(r.geometry).toEqual({ type: 'Point', coordinates: [-73.5, 45.5] });
    });

    it('parses comma-separated negative pair', () => {
        const r = parseGeometryInput('-45.5,-73.5', 'Point');
        expect(r.error).toBeNull();
        expect(r.geometry).toEqual({ type: 'Point', coordinates: [-73.5, -45.5] });
    });

    it('rejects when first value is out of latitude range', () => {
        // 91 cannot be a latitude; user likely swapped the order.
        const r = parseGeometryInput('91, 45', 'Point');
        expect(r.geometry).toBeNull();
        expect(r.error).toMatch(/latitude/i);
    });
});

describe('parseGeometryInput - prose does not route to DMS', () => {
    it('rejects "not sure" with the generic unrecognized message', () => {
        const r = parseGeometryInput('not sure', 'Point');
        expect(r.geometry).toBeNull();
        expect(r.error).toMatch(/unrecognized/i);
    });

    it('rejects "Main Street West"', () => {
        const r = parseGeometryInput('Main Street West', 'Point');
        expect(r.geometry).toBeNull();
        expect(r.error).toMatch(/unrecognized/i);
    });
});

describe('parseGeometryInput - geom_type matching', () => {
    it('rejects a Point when widget expects a LineString', () => {
        const text = '{"type":"Point","coordinates":[-73.5,45.5]}';
        const r = parseGeometryInput(text, 'LineString');
        expect(r.geometry).toBeNull();
        expect(r.error).toMatch(/line ?string/i);
    });

    it('rejects a LineString when widget expects a Point', () => {
        const text = '{"type":"LineString","coordinates":[[-73.5,45.5],[-73.4,45.6]]}';
        const r = parseGeometryInput(text, 'Point');
        expect(r.geometry).toBeNull();
        expect(r.error).toMatch(/point/i);
    });

    it('accepts any geometry when widget type is "Geometry"', () => {
        const pt = parseGeometryInput('{"type":"Point","coordinates":[-73.5,45.5]}', 'Geometry');
        expect(pt.error).toBeNull();
        const line = parseGeometryInput(
            '{"type":"LineString","coordinates":[[-73.5,45.5],[-73.4,45.6]]}',
            'Geometry',
        );
        expect(line.error).toBeNull();
    });

    it('normalizes widget type "LINESTRING" (all caps) to LineString', () => {
        const text = '{"type":"LineString","coordinates":[[-73.5,45.5],[-73.4,45.6]]}';
        const r = parseGeometryInput(text, 'LINESTRING');
        expect(r.error).toBeNull();
        expect(r.geometry?.type).toBe('LineString');
    });
});

describe('parseGeometryInput - coordinate validation', () => {
    it('rejects longitude > 180', () => {
        const r = parseGeometryInput('{"type":"Point","coordinates":[181,45]}', 'Point');
        expect(r.geometry).toBeNull();
        expect(r.error).toMatch(/longitude/i);
    });

    it('rejects longitude < -180', () => {
        const r = parseGeometryInput('{"type":"Point","coordinates":[-181,45]}', 'Point');
        expect(r.geometry).toBeNull();
        expect(r.error).toMatch(/longitude/i);
    });

    it('rejects latitude > 90', () => {
        const r = parseGeometryInput('{"type":"Point","coordinates":[0,91]}', 'Point');
        expect(r.geometry).toBeNull();
        expect(r.error).toMatch(/latitude/i);
    });

    it('rejects latitude < -90', () => {
        const r = parseGeometryInput('{"type":"Point","coordinates":[0,-91]}', 'Point');
        expect(r.geometry).toBeNull();
        expect(r.error).toMatch(/latitude/i);
    });

    it('accepts boundary values', () => {
        const r = parseGeometryInput('{"type":"Point","coordinates":[180,90]}', 'Point');
        expect(r.error).toBeNull();
    });

    it('rejects non-finite coordinate', () => {
        const r = parseGeometryInput('{"type":"Point","coordinates":["foo",45]}', 'Point');
        expect(r.geometry).toBeNull();
        expect(r.error).not.toBeNull();
    });
});

describe('parseGeometryInput - malformed', () => {
    it('rejects gibberish', () => {
        const r = parseGeometryInput('this is not geometry', 'Point');
        expect(r.geometry).toBeNull();
        expect(r.error).not.toBeNull();
    });

    it('rejects JSON without a type', () => {
        const r = parseGeometryInput('{"coordinates":[-73.5,45.5]}', 'Point');
        expect(r.geometry).toBeNull();
        expect(r.error).not.toBeNull();
    });

    it('rejects unsupported geometry type', () => {
        const r = parseGeometryInput(
            '{"type":"MultiPoint","coordinates":[[-73.5,45.5],[-73.4,45.6]]}',
            'Geometry',
        );
        expect(r.geometry).toBeNull();
        expect(r.error).toMatch(/multipoint|unsupported/i);
    });
});

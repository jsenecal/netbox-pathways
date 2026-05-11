/**
 * Forgiving free-text geometry parser for the Coordinates tab of the map widget.
 *
 * Accepts GeoJSON (Geometry/Feature/FeatureCollection), WKT, DMS (with or
 * without N/S/E/W hemispheres), and bare decimal lat,lon pairs in Google
 * Maps order (latitude first). All coordinates are emitted as EPSG:4326
 * [longitude, latitude] per RFC 7946.
 *
 * See issue #32.
 */

export type GeomType = 'Point' | 'LineString' | 'Polygon' | 'Geometry';

export interface ParseResult {
    geometry: GeoJSON.Geometry | null;
    error: string | null;
}

const SUPPORTED_TYPES = ['Point', 'LineString', 'Polygon'] as const;

function ok(geometry: GeoJSON.Geometry): ParseResult {
    return { geometry, error: null };
}

function fail(message: string): ParseResult {
    return { geometry: null, error: message };
}

function empty(): ParseResult {
    return { geometry: null, error: null };
}

function normalizeGeomType(geomType: string): GeomType {
    const stripped = geomType.replace(/\s+/g, '').toLowerCase();
    switch (stripped) {
        case 'point':
            return 'Point';
        case 'linestring':
            return 'LineString';
        case 'polygon':
            return 'Polygon';
        case 'geometry':
        case '':
            return 'Geometry';
        default:
            return 'Geometry';
    }
}

function inRange(coord: unknown): coord is [number, number] {
    if (!Array.isArray(coord) || coord.length < 2) return false;
    return typeof coord[0] === 'number' && typeof coord[1] === 'number'
        && Number.isFinite(coord[0]) && Number.isFinite(coord[1]);
}

function validatePoint(c: [number, number]): string | null {
    const [lon, lat] = c;
    if (lon < -180 || lon > 180) return `Longitude ${lon} out of range [-180, 180].`;
    if (lat < -90 || lat > 90) return `Latitude ${lat} out of range [-90, 90].`;
    return null;
}

function validateGeometryShape(g: GeoJSON.Geometry): string | null {
    switch (g.type) {
        case 'Point': {
            if (!inRange(g.coordinates)) return 'Point coordinates must be two finite numbers [lon, lat].';
            return validatePoint(g.coordinates as [number, number]);
        }
        case 'LineString': {
            const coords = g.coordinates;
            if (!Array.isArray(coords) || coords.length < 2) {
                return 'LineString requires at least two coordinate pairs.';
            }
            for (const c of coords) {
                if (!inRange(c)) return 'LineString coordinates must be pairs of finite numbers.';
                const err = validatePoint(c as [number, number]);
                if (err) return err;
            }
            return null;
        }
        case 'Polygon': {
            const rings = g.coordinates;
            if (!Array.isArray(rings) || rings.length === 0) return 'Polygon requires at least one ring.';
            for (const ring of rings) {
                if (!Array.isArray(ring) || ring.length < 4) {
                    return 'Polygon rings need at least four coordinate pairs (closed).';
                }
                for (const c of ring) {
                    if (!inRange(c)) return 'Polygon coordinates must be pairs of finite numbers.';
                    const err = validatePoint(c as [number, number]);
                    if (err) return err;
                }
            }
            return null;
        }
        default:
            return `Unsupported geometry type "${(g as { type: string }).type}".`;
    }
}

function checkTypeMatch(g: GeoJSON.Geometry, expected: GeomType): string | null {
    if (expected === 'Geometry') return null;
    if (g.type !== expected) {
        return `Expected ${expected}, got ${g.type}.`;
    }
    return null;
}

function looksLikeJson(text: string): boolean {
    const first = text[0];
    return first === '{' || first === '[';
}

function looksLikeWkt(text: string): boolean {
    return /^\s*(point|linestring|polygon|multipoint|multilinestring|multipolygon)\s*\(/i.test(text);
}

function looksLikeDmsWithHemisphere(text: string): boolean {
    // Require a digit immediately before a hemisphere letter so prose like
    // "not sure" or "Main St West" doesn't route here.
    return /\d[°dD'"ms\s:]*[NSEWnsew]/.test(text);
}

function tokenizeNumbers(text: string): string[] {
    // Split on any DMS separator or whitespace/comma; keep numeric tokens.
    return text.split(/[°'"dDmMsS:,\s]+/).filter((t) => t.length > 0 && /^-?\d/.test(t));
}

// ---------------------------------------------------------------------------
// GeoJSON
// ---------------------------------------------------------------------------

function parseJson(text: string): ParseResult {
    let parsed: unknown;
    try {
        parsed = JSON.parse(text);
    } catch {
        return fail('Invalid JSON.');
    }
    return extractGeometry(parsed);
}

function extractGeometry(obj: unknown): ParseResult {
    if (!obj || typeof obj !== 'object') return fail('JSON value is not an object.');
    const o = obj as { type?: string; geometry?: unknown; features?: unknown };
    if (typeof o.type !== 'string') return fail('JSON object is missing a "type" field.');

    if (o.type === 'Feature') {
        if (!o.geometry) return fail('Feature has no geometry.');
        return extractGeometry(o.geometry);
    }
    if (o.type === 'FeatureCollection') {
        const features = Array.isArray(o.features) ? o.features : [];
        if (features.length === 0) return fail('FeatureCollection has no features.');
        return extractGeometry((features[0] as { geometry?: unknown }).geometry);
    }
    if ((SUPPORTED_TYPES as readonly string[]).includes(o.type)) {
        return ok(obj as GeoJSON.Geometry);
    }
    return fail(`Unsupported geometry type "${o.type}".`);
}

// ---------------------------------------------------------------------------
// WKT
// ---------------------------------------------------------------------------

function parseWkt(text: string): ParseResult {
    const match = text.trim().match(/^(point|linestring|polygon)\s*\(([\s\S]*)\)\s*$/i);
    if (!match) return fail('Unrecognized WKT.');
    const kind = match[1].toLowerCase();
    const body = match[2];

    if (kind === 'point') {
        const coord = parseWktCoord(body.trim());
        if (!coord) return fail('Invalid POINT coordinates.');
        return ok({ type: 'Point', coordinates: coord });
    }
    if (kind === 'linestring') {
        const coords = body.split(',').map((s) => parseWktCoord(s.trim()));
        if (coords.some((c) => !c)) return fail('Invalid LINESTRING coordinates.');
        return ok({ type: 'LineString', coordinates: coords as [number, number][] });
    }
    if (kind === 'polygon') {
        // POLYGON((lon lat, lon lat, ...), (...))
        const ringStrs = body.match(/\(([^()]+)\)/g);
        if (!ringStrs || ringStrs.length === 0) return fail('Invalid POLYGON rings.');
        const rings: [number, number][][] = [];
        for (const r of ringStrs) {
            const inner = r.slice(1, -1);
            const pts = inner.split(',').map((s) => parseWktCoord(s.trim()));
            if (pts.some((p) => !p)) return fail('Invalid POLYGON coordinates.');
            rings.push(pts as [number, number][]);
        }
        return ok({ type: 'Polygon', coordinates: rings });
    }
    return fail('Unsupported WKT type.');
}

function parseWktCoord(s: string): [number, number] | null {
    const parts = s.trim().split(/\s+/);
    if (parts.length < 2) return null;
    const lon = Number(parts[0]);
    const lat = Number(parts[1]);
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
    return [lon, lat];
}

// ---------------------------------------------------------------------------
// DMS (point only, requires N/S/E/W disambiguation)
// ---------------------------------------------------------------------------

const DMS_RE = /(-?\d+(?:\.\d+)?)[°dD\s:]+(\d+(?:\.\d+)?)(?:['m\s:]+(\d+(?:\.\d+)?))?["s\s]*([NSEWnsew])/g;

function parseDms(text: string): ParseResult {
    const tokens: { deg: number; min: number; sec: number; hemi: string }[] = [];
    const re = new RegExp(DMS_RE.source, 'gi');
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
        tokens.push({
            deg: Number(m[1]),
            min: Number(m[2] || 0),
            sec: Number(m[3] || 0),
            hemi: m[4].toUpperCase(),
        });
    }
    if (tokens.length !== 2) {
        return fail('Could not parse DMS pair. Expected "DD MM SS N/S DD MM SS E/W".');
    }

    let lat: number | null = null;
    let lon: number | null = null;
    for (const t of tokens) {
        const sign = (t.hemi === 'S' || t.hemi === 'W') ? -1 : 1;
        const decimal = sign * (Math.abs(t.deg) + t.min / 60 + t.sec / 3600);
        if (t.hemi === 'N' || t.hemi === 'S') lat = decimal;
        else lon = decimal;
    }
    if (lat === null || lon === null) {
        return fail('DMS pair must include one N/S and one E/W hemisphere.');
    }
    return ok({ type: 'Point', coordinates: [lon, lat] });
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

function parseDecimalPair(latRaw: string, lonRaw: string): ParseResult {
    const lat = Number(latRaw);
    const lon = Number(lonRaw);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        return fail('Latitude and longitude must be numbers.');
    }
    return ok({ type: 'Point', coordinates: [lon, lat] });
}

function parseDmsTriple(deg: string, min: string, sec: string): number | null {
    const d = Number(deg);
    const m = Number(min);
    const s = Number(sec);
    if (!Number.isFinite(d) || !Number.isFinite(m) || !Number.isFinite(s)) return null;
    const sign = d < 0 || Object.is(d, -0) ? -1 : 1;
    return sign * (Math.abs(d) + m / 60 + s / 3600);
}

function parseNumericTokens(tokens: string[]): ParseResult {
    if (tokens.length === 2) {
        return parseDecimalPair(tokens[0], tokens[1]);
    }
    if (tokens.length === 6) {
        const lat = parseDmsTriple(tokens[0], tokens[1], tokens[2]);
        const lon = parseDmsTriple(tokens[3], tokens[4], tokens[5]);
        if (lat === null || lon === null) return fail('Invalid DMS components.');
        return ok({ type: 'Point', coordinates: [lon, lat] });
    }
    return fail('Unrecognized input. Paste GeoJSON, WKT, DMS, or lat,lon decimals.');
}

export function parseGeometryInput(text: string, geomType: string): ParseResult {
    const trimmed = text.trim();
    if (!trimmed) return empty();

    const expected = normalizeGeomType(geomType);

    let result: ParseResult;
    if (looksLikeJson(trimmed)) {
        result = parseJson(trimmed);
    } else if (looksLikeWkt(trimmed)) {
        result = parseWkt(trimmed);
    } else if (looksLikeDmsWithHemisphere(trimmed)) {
        result = parseDms(trimmed);
    } else {
        const tokens = tokenizeNumbers(trimmed);
        if (tokens.length === 0) {
            return fail('Unrecognized input. Paste GeoJSON, WKT, DMS, or lat,lon decimals.');
        }
        result = parseNumericTokens(tokens);
    }

    if (result.error || !result.geometry) return result;

    const shapeErr = validateGeometryShape(result.geometry);
    if (shapeErr) return fail(shapeErr);

    const typeErr = checkTypeMatch(result.geometry, expected);
    if (typeErr) return fail(typeErr);

    return result;
}

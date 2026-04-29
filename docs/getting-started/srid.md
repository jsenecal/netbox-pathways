# SRID Selection

The `srid` setting in `PLUGINS_CONFIG['netbox_pathways']` is the single most important
decision you make before installing this plugin. It determines the spatial reference
system used for every geometry column the plugin creates in your database.

!!! danger "The SRID is immutable after first migration"
    The `srid` value is baked into PostGIS geometry columns at migration time.
    Changing the setting after data has been loaded **will not** re-project the
    stored coordinates. Geometries will retain their original numeric values but
    PostGIS will interpret them as belonging to the new CRS, which corrupts every
    spatial query and every map render. There is no automatic recovery.

    Choose your SRID carefully. Test the plugin on an empty database first if you
    are unsure.

## What an SRID Is

An SRID (Spatial Reference Identifier) is a numeric handle for a coordinate
reference system. Most production deployments use an
[EPSG](https://epsg.io/) code, for example `4326` for WGS84 latitude/longitude
or `3857` for Web Mercator. The plugin stores every `Point`, `LineString`, and
`Polygon` field with the SRID you configure.

Storage SRID is independent of how data is exchanged with the map and the
GeoJSON API. Both always use EPSG:4326 (WGS84). The plugin transforms in and
out of your storage SRID automatically using PostGIS `ST_Transform`.

## How To Choose

The right SRID depends on the geographic extent of your network and the kinds
of measurements you want PostGIS to make accurately.

### Small geographic footprint, accurate distances

If all your infrastructure fits inside one country or one UTM zone, pick a
projected CRS measured in meters. Length, area, and buffer queries will return
real-world meters without further math. Examples:

| EPSG    | CRS                                              | Best for                       |
|---------|--------------------------------------------------|--------------------------------|
| `3348`  | NAD83(CSRS) / Statistics Canada Lambert          | All of Canada                  |
| `2154`  | RGF93 / Lambert-93                               | Mainland France                |
| `25832` | ETRS89 / UTM zone 32N                            | Central Europe (e.g. Germany)  |
| `32188` | NAD83 / MTM zone 8                               | Quebec, Canada                 |
| `27700` | OSGB 1936 / British National Grid                | Great Britain                  |
| `3577`  | GDA94 / Australian Albers                        | Australia                      |
| `2272`  | NAD83 / Pennsylvania South (US ft)               | Pennsylvania, USA              |

### Global or mixed extent

If your network spans multiple continents, a single projected CRS will distort
distances at the edges. WGS84 stores raw degrees and is universally supported.
Web Mercator stores meters projected for tile maps but distorts area near the
poles.

| EPSG   | CRS                              | Notes                                        |
|--------|----------------------------------|----------------------------------------------|
| `4326` | WGS84 (degrees lat/lon)          | Global. Distance queries return degrees.     |
| `3857` | WGS 84 / Pseudo-Mercator         | What slippy-map tiles use. Meters but warped near poles. |

### Inside-plant only

If every structure and pathway is inside a single building, you can still use
WGS84 (degrees). You will not benefit from a projected CRS at building scale,
and using one designed for a wider area introduces complexity without payoff.

## Setting the SRID

In your NetBox `configuration.py`:

```python
PLUGINS_CONFIG = {
    "netbox_pathways": {
        "srid": 3348,
    },
}
```

The setting is `required_settings` on `PluginConfig`. Starting NetBox without
it will raise `ImproperlyConfigured` from `netbox_pathways.geo.get_srid()` on
first request.

## Verifying the Configured SRID

After running migrations, confirm the column SRID matches your setting:

```sql
SELECT f_table_name, f_geometry_column, srid
FROM geometry_columns
WHERE f_table_schema = 'public'
  AND f_table_name LIKE 'netbox_pathways_%';
```

Every row should report the SRID you set. If any row reports a different
value, your configuration was changed after migration and your geometry data
is now misaligned.

## Recovering From a Wrong SRID

There is no safe one-line fix. If you discover the SRID is wrong after data
has been loaded, you must:

1. Take a database backup before doing anything else.
2. Determine which CRS the existing coordinates were actually authored in
   (the old setting), call this `OLD_SRID`. Determine the desired storage SRID,
   call this `NEW_SRID`.
3. For every geometry column, run a PostGIS update that reinterprets the data
   in `OLD_SRID` and re-projects it to `NEW_SRID`:

    ```sql
    -- Example for the structures table
    UPDATE netbox_pathways_structure
    SET location = ST_Transform(ST_SetSRID(location, OLD_SRID), NEW_SRID);

    -- Update the column constraint
    SELECT UpdateGeometrySRID(
      'netbox_pathways_structure',
      'location',
      NEW_SRID
    );
    ```

4. Repeat for every geometry column on every pathways model
   (`structure.location`, `pathway.path`, `sitegeometry.geometry`,
   `circuitgeometry.path`).
5. Update `PLUGINS_CONFIG['netbox_pathways']['srid']` to `NEW_SRID` and restart
   NetBox.

This is a database-administrator operation. Do it on a copy of production data
before touching production.

## Why The Plugin Hard-Codes Storage SRID

Mixing per-row SRIDs in a column is legal in PostGIS but forces every spatial
query to specify the right SRID at call time, breaks spatial indexes, and
makes development much more error prone. The plugin uses one SRID throughout
the database and transforms only at the API boundary, where performance is
amortised over per-row serialisation work.

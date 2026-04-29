# PostGIS Setup

NetBox Pathways requires PostGIS. NetBox itself runs against plain PostgreSQL
out of the box, so adding this plugin means changing your database
configuration. This page covers what to install, how to enable the extension,
and how to configure NetBox to use the PostGIS database backend.

## Required Versions

| Component        | Minimum |
|------------------|---------|
| PostgreSQL       | 16      |
| PostGIS          | 3.4     |
| GDAL             | 3.x     |
| GEOS             | 3.10    |
| PROJ             | 8       |

GDAL, GEOS, and PROJ are C libraries used by Django's GIS layer. They must be
installed on the host running the NetBox web workers, not just on the database
server.

## Installing System Libraries

=== "Debian / Ubuntu"

    ```bash
    sudo apt-get update
    sudo apt-get install -y \
        gdal-bin libgdal-dev \
        libgeos-dev \
        libproj-dev \
        binutils
    ```

=== "RHEL / Rocky / AlmaLinux"

    ```bash
    sudo dnf install -y epel-release
    sudo dnf install -y \
        gdal gdal-devel \
        geos geos-devel \
        proj proj-devel
    ```

=== "Alpine (Docker)"

    ```dockerfile
    RUN apk add --no-cache \
        gdal gdal-dev \
        geos geos-dev \
        proj proj-dev \
        binutils
    ```

## Enabling the PostGIS Extension

Connect to the NetBox database as a superuser and run:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

Verify it was installed:

```sql
SELECT PostGIS_Version();
```

You should see something like `3.4 USE_GEOS=1 USE_PROJ=1 USE_STATS=1`.

## Database Backend Configuration

In `configuration.py`, change the `DATABASE` engine from the default
PostgreSQL backend to the PostGIS one:

```python
DATABASE = {
    "ENGINE": "django.contrib.gis.db.backends.postgis",
    "NAME": "netbox",
    "USER": "netbox",
    "PASSWORD": "...",
    "HOST": "localhost",
    "PORT": "",
    "CONN_MAX_AGE": 300,
}
```

!!! warning
    The plain `django.db.backends.postgresql` backend will appear to work
    until the first migration that creates a geometry column, which then
    fails because the backend has no idea what `geometry()` is. Always set
    the PostGIS backend before running `migrate netbox_pathways`.

## Migrating an Existing NetBox Database

If you have an established NetBox install on plain PostgreSQL and are adding
this plugin to it:

1. Take a backup. `pg_dump` the entire NetBox database.
2. Install PostGIS system packages on the database server, restart Postgres.
3. Run `CREATE EXTENSION postgis;` on the existing database. No data
   migration is required for existing core tables; PostGIS lives alongside
   plain PostgreSQL features.
4. Switch `DATABASE['ENGINE']` to the PostGIS backend.
5. Choose your SRID. See [SRID Selection](srid.md). This decision is
   permanent.
6. Run `python manage.py migrate netbox_pathways`.
7. Restart `netbox` and `netbox-rq` services.

## Containerised Setup (DevContainer / Docker Compose)

The plugin's bundled DevContainer uses `postgis/postgis:16-3.4` as the
database image. If you are building your own Compose stack, use that image
or another `postgis` tag pinned to the version above.

```yaml
services:
  postgres:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_DB: netbox
      POSTGRES_USER: netbox
      POSTGRES_PASSWORD: netbox
```

The official NetBox Docker image already bundles GDAL, so no additional
build steps are needed on the application side.

## Verifying The Stack

After installing the plugin, run the Django system check:

```bash
python manage.py check netbox_pathways
```

It should report no issues. Then create a test structure through the UI or
the API. If geometry input fails with errors mentioning `postgis`, `gdal`,
or `geos`, one of the system libraries is missing or the database backend is
still set to plain PostgreSQL.

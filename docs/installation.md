# Installation

## Prerequisites

NetBox Pathways requires:

- **NetBox 4.5.3+** with PostGIS-enabled PostgreSQL
- **PostgreSQL 16+** with the **PostGIS 3.4** extension
- **GDAL**, **GEOS**, and **PROJ** system libraries (required by GeoDjango)

### PostGIS Setup

Your PostgreSQL database must have PostGIS enabled. If you haven't already:

```sql
CREATE EXTENSION postgis;
```

Your NetBox `configuration.py` must use the PostGIS database backend:

```python
DATABASE = {
    'ENGINE': 'django.contrib.gis.db.backends.postgis',
    'NAME': 'netbox',
    'USER': 'netbox',
    'PASSWORD': 'your-password',
    'HOST': 'localhost',
    'PORT': '',
}
```

!!! warning
    The standard `django.db.backends.postgresql` engine will **not** work. You must use `django.contrib.gis.db.backends.postgis`.

### System Libraries

On Debian/Ubuntu:

```bash
sudo apt install gdal-bin libgdal-dev libgeos-dev libproj-dev
```

On RHEL/CentOS:

```bash
sudo dnf install gdal gdal-devel geos geos-devel proj proj-devel
```

## Install the Plugin

```bash
pip install netbox-pathways
```

Or install from source:

```bash
pip install git+https://github.com/jsenecal/netbox-pathways.git
```

## Configure NetBox

Add the plugin to `configuration.py`:

```python
PLUGINS = ['netbox_pathways']
```

Optional settings (shown with defaults):

```python
PLUGINS_CONFIG = {
    'netbox_pathways': {
        'map_center_lat': 45.5017,
        'map_center_lon': -73.5673,
        'map_zoom': 10,
    }
}
```

## Run Migrations

```bash
cd /opt/netbox/netbox
python manage.py migrate
```

## Collect Static Files

```bash
python manage.py collectstatic --no-input
```

## Restart NetBox

```bash
sudo systemctl restart netbox netbox-rq
```

## Verify Installation

Navigate to your NetBox instance. You should see **Pathways** in the plugin menu with entries for Structures, Conduits, Aerial Spans, and more.

You can also verify via the API:

```bash
curl -H "Authorization: Token <your-token>" \
  https://your-netbox/api/plugins/pathways/structures/
```

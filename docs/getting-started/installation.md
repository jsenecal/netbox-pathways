# Installation

## Prerequisites

- **NetBox** 4.5.3 or later
- **PostgreSQL** 16+ with **PostGIS 3.4** extension
- **GDAL**, **GEOS**, and **PROJ** system libraries
- **Python** 3.12+

## 1. Install PostGIS

### Enable the Extension

Connect to your NetBox database and enable PostGIS:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

### Configure the Database Backend

In your NetBox `configuration.py`, set the database engine to the PostGIS backend:

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
    The standard `django.db.backends.postgresql` engine will **not** work. You must use the PostGIS backend for geographic field support.

### Install System Libraries

=== "Debian / Ubuntu"

    ```bash
    sudo apt-get install -y gdal-bin libgdal-dev libgeos-dev libproj-dev
    ```

=== "RHEL / CentOS"

    ```bash
    sudo dnf install -y gdal gdal-devel geos geos-devel proj proj-devel
    ```

## 2. Install the Plugin

### From PyPI

```bash
pip install netbox-pathways
```

### From Source

```bash
git clone https://github.com/jsenecal/netbox-pathways.git
cd netbox-pathways
pip install -e .
```

## 3. Configure NetBox

Add the plugin to your `configuration.py`:

```python
PLUGINS = ['netbox_pathways']

PLUGINS_CONFIG = {
    'netbox_pathways': {
        'map_center_lat': 45.5,    # Default map center latitude
        'map_center_lon': -73.5,   # Default map center longitude
        'map_zoom': 13,            # Default map zoom level
    }
}
```

## 4. Run Migrations

```bash
cd /opt/netbox
python manage.py migrate netbox_pathways
```

## 5. Collect Static Files

```bash
python manage.py collectstatic --no-input
```

## 6. Restart NetBox

```bash
sudo systemctl restart netbox netbox-rq
```

## Verify Installation

1. Log into the NetBox web interface
2. Navigate to **Plugins > Pathways**
3. You should see the Pathways navigation menu with Structures, Pathways, Conduit Banks, and other model sections
4. Navigate to **Plugins > Pathways > Map** to verify the interactive map loads

!!! tip
    If the map does not load, check your browser console for JavaScript errors and verify that static files were collected successfully.

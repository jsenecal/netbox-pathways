"""Worker function for multiprocess geodata import.

This module is deliberately free of Django model imports at module level,
so it can be safely pickled and sent to spawned processes.
"""

import os
import sys


def save_batch(model_map_key, batch_rows, geom_field):
    """Save a batch of model instances in a worker process.

    Geometry objects are passed as EWKT strings and reconstructed here,
    since GEOS objects can't be pickled across process boundaries.
    FK references are passed as ('__fk__', 'app_label.model_name', pk) tuples.
    """
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
    if '/opt/netbox/netbox' not in sys.path:
        sys.path.insert(0, '/opt/netbox/netbox')
    import django
    django.setup()

    from django.apps import apps
    from django.contrib.gis.geos import GEOSGeometry
    from django.db import connection

    from netbox_pathways.management.commands.import_geodata import MODEL_MAP

    connection.ensure_connection()

    model_class = MODEL_MAP[model_map_key]
    saved = 0
    errors = []
    for row in batch_rows:
        try:
            kwargs = {}
            for key, value in row.items():
                if key == geom_field:
                    kwargs[key] = GEOSGeometry(value)
                elif isinstance(value, tuple) and len(value) == 3 and value[0] == '__fk__':
                    fk_model = apps.get_model(value[1])
                    kwargs[key] = fk_model(pk=value[2])
                else:
                    kwargs[key] = value
            obj = model_class(**kwargs)
            obj.save()
            saved += 1
        except Exception as e:
            errors.append(str(e))

    connection.close()
    return saved, errors

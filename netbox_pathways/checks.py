"""
System checks for the netbox_pathways plugin.

The storage SRID is baked into PostGIS columns at migrate time, but
get_srid() is read from PLUGINS_CONFIG at form/serializer save time. If
the two ever drift apart -- either because a migration shipped with a
hardcoded SRID, or because an operator edited PLUGINS_CONFIG after
applying migrations -- inserts fail with a SRID mismatch and crash the
end user back to the home page (see issue #5).

This module introspects geometry_columns and emits a checks.Error for
every column whose stored SRID does not match get_srid(), with a hint
that points at both remediation paths (revert config, or write an
ST_Transform migration).
"""

from django.apps import apps
from django.core.checks import Error
from django.db import connection
from django.db.utils import OperationalError, ProgrammingError

from .geo import get_srid

CHECK_ID = "netbox_pathways.E001"


def _introspect_column_srids(connection, app_label):
    """Return {(table, column): srid} for geometry columns in the app's tables."""
    if connection.vendor != "postgresql":
        return {}
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT f_table_name, f_geometry_column, srid FROM geometry_columns WHERE f_table_name LIKE %s",
                [f"{app_label}_%"],
            )
            return {(row[0], row[1]): row[2] for row in cursor.fetchall()}
    except (OperationalError, ProgrammingError):
        return {}


def check_geometry_column_srids(app_configs=None, **kwargs):
    """Compare introspected column SRIDs to PLUGINS_CONFIG['netbox_pathways']['srid']."""
    from django.core.exceptions import ImproperlyConfigured

    try:
        expected_srid = get_srid()
    except ImproperlyConfigured:
        return []

    actual = _introspect_column_srids(connection, "netbox_pathways")
    if not actual:
        return []

    try:
        models = apps.get_app_config("netbox_pathways").get_models()
    except LookupError:
        return []

    errors = []
    for model in models:
        table = model._meta.db_table
        for field in model._meta.get_fields():
            if not hasattr(field, "srid") or field.srid is None:
                continue
            actual_srid = actual.get((table, field.column))
            if actual_srid is None or actual_srid == expected_srid:
                continue
            errors.append(
                Error(
                    f"Geometry column {table}.{field.column} has SRID {actual_srid}, "
                    f"but PLUGINS_CONFIG['netbox_pathways']['srid'] is {expected_srid}. "
                    "Form submissions and API writes will fail with 'Geometry SRID does "
                    "not match column SRID'.",
                    hint=(
                        "Storage SRID is immutable after migrations apply. Either "
                        f"set PLUGINS_CONFIG['netbox_pathways']['srid'] = {actual_srid} "
                        "to match the existing columns, or write a data migration that "
                        f"runs ST_Transform(<column>, {expected_srid}) on every affected "
                        "row before re-typing the column."
                    ),
                    id=CHECK_ID,
                    obj=model,
                )
            )
    return errors

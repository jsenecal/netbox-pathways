"""Tests for SRID drift system check and migration consistency."""

import importlib
from copy import deepcopy
from unittest.mock import MagicMock, patch

from django.core.checks import Error
from django.db import connection
from django.db.utils import ProgrammingError

from netbox_pathways.checks import (
    _introspect_column_srids,
    check_geometry_column_srids,
)


class TestMigrationSrid:
    """Migrations must derive SRID from get_srid(), never from a literal."""

    def test_circuit_geometry_path_srid_follows_config(self, settings):
        settings.PLUGINS_CONFIG = deepcopy(settings.PLUGINS_CONFIG)
        settings.PLUGINS_CONFIG.setdefault("netbox_pathways", {})["srid"] = 3857

        mod = importlib.import_module("netbox_pathways.migrations.0004_circuit_geometry")
        importlib.reload(mod)

        operation = mod.Migration.operations[0]
        fields_dict = dict(operation.fields)
        assert fields_dict["path"].srid == 3857


class TestIntrospectColumnSrids:
    def test_returns_empty_for_non_postgres(self):
        fake_conn = MagicMock()
        fake_conn.vendor = "sqlite"
        assert _introspect_column_srids(fake_conn, "netbox_pathways") == {}

    def test_returns_empty_on_db_error(self):
        fake_conn = MagicMock()
        fake_conn.vendor = "postgresql"
        cursor = fake_conn.cursor.return_value.__enter__.return_value
        cursor.execute.side_effect = ProgrammingError("relation does not exist")
        assert _introspect_column_srids(fake_conn, "netbox_pathways") == {}

    def test_introspects_real_columns(self, db):
        result = _introspect_column_srids(connection, "netbox_pathways")
        assert ("netbox_pathways_structure", "location") in result


class TestCheckGeometryColumnSrids:
    def test_silent_when_srid_unconfigured(self):
        from django.core.exceptions import ImproperlyConfigured

        with patch("netbox_pathways.checks.get_srid", side_effect=ImproperlyConfigured()):
            assert check_geometry_column_srids() == []

    def test_silent_when_no_columns_introspected(self):
        with patch("netbox_pathways.checks._introspect_column_srids", return_value={}):
            assert check_geometry_column_srids() == []

    def test_no_errors_when_columns_match_config(self, db):
        assert check_geometry_column_srids() == []

    def test_reports_error_on_mismatch(self, db):
        with patch("netbox_pathways.checks.get_srid", return_value=999):
            errors = check_geometry_column_srids()
        assert errors, "expected at least one mismatch error"
        assert all(isinstance(e, Error) for e in errors)
        assert all(e.id == "netbox_pathways.E001" for e in errors)
        first = errors[0]
        assert "999" in first.msg
        assert "PLUGINS_CONFIG" in first.hint
        assert "ST_Transform" in first.hint

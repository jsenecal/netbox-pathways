import datetime

import pytest

from netbox_pathways.management.commands.import_geodata import (
    TRANSFORMS,
    Command,
    _matches_null_value,
)


class TestMatchesNullValue:
    def test_value_python_none_matches(self):
        assert _matches_null_value(None, [0]) is True

    def test_zero_float_matches_int_zero_sentinel(self):
        assert _matches_null_value(0.0, [0]) is True

    def test_zero_int_matches_float_zero_sentinel(self):
        assert _matches_null_value(0, [0.0]) is True

    def test_string_zero_matches_numeric_sentinel(self):
        assert _matches_null_value("0", [0.0]) is True
        assert _matches_null_value("0.0", [0]) is True

    def test_non_numeric_sentinel_string_match(self):
        assert _matches_null_value("N/A", ["N/A"]) is True

    def test_negative_sentinel(self):
        assert _matches_null_value(-1, [-1, 9999]) is True

    def test_nonzero_value_does_not_match_zero_sentinels(self):
        assert _matches_null_value(1.5, [0, 0.0]) is False

    def test_nonmatching_string_does_not_match(self):
        assert _matches_null_value("hello", [0]) is False

    def test_empty_null_values_returns_false(self):
        assert _matches_null_value(0.0, []) is False

    def test_none_in_null_values_list_is_skipped(self):
        # None entries in the list should be ignored, not crash
        assert _matches_null_value(0, [None, 0]) is True
        assert _matches_null_value(1, [None]) is False


class TestTransforms:
    """Cover the TRANSFORMS lambdas used by _apply_field_spec and aggregate fields."""

    def test_year_to_date_positive_year(self):
        assert TRANSFORMS["year_to_date"]("1995") == datetime.date(1995, 1, 1)

    def test_year_to_date_zero_returns_none(self):
        # Zero is treated as "no data" so we get None.
        assert TRANSFORMS["year_to_date"](0) is None

    def test_year_to_date_none_returns_none(self):
        assert TRANSFORMS["year_to_date"](None) is None

    def test_to_int_string(self):
        assert TRANSFORMS["to_int"]("42") == 42

    def test_to_int_none(self):
        assert TRANSFORMS["to_int"](None) is None

    def test_to_float_string(self):
        assert TRANSFORMS["to_float"]("3.14") == pytest.approx(3.14)

    def test_to_float_none(self):
        assert TRANSFORMS["to_float"](None) is None

    def test_to_bool_string_one_is_true(self):
        assert TRANSFORMS["to_bool"]("1") is True

    def test_to_bool_string_zero_is_false(self):
        assert TRANSFORMS["to_bool"]("0") is False

    def test_to_bool_none_returns_false(self):
        assert TRANSFORMS["to_bool"](None) is False

    def test_to_str_coerces(self):
        assert TRANSFORMS["to_str"](42) == "42"

    def test_to_str_none_returns_empty_string(self):
        assert TRANSFORMS["to_str"](None) == ""

    def test_boolean_flag_truthy(self):
        assert TRANSFORMS["boolean_flag"]("1") is True

    def test_boolean_flag_none_is_false(self):
        assert TRANSFORMS["boolean_flag"](None) is False


class _FakeFeature:
    """Minimal stand-in for an OGR Feature that supports .get(field)."""

    def __init__(self, data):
        self._data = data

    def get(self, key):
        return self._data.get(key)


class TestPassesFilters:
    """Cover Command._passes_filters: per-field equality with stringified compare."""

    def _cmd(self):
        # Instantiate without invoking BaseCommand's heavy init plumbing for handle().
        return Command()

    def test_empty_filters_always_passes(self):
        feature = _FakeFeature({"status": "ACTIVE"})
        assert self._cmd()._passes_filters(feature, {}) is True

    def test_all_filters_match(self):
        feature = _FakeFeature({"status": "ACTIVE", "kind": "pole"})
        assert self._cmd()._passes_filters(feature, {"status": "ACTIVE", "kind": "pole"}) is True

    def test_single_mismatch_fails(self):
        feature = _FakeFeature({"status": "ACTIVE"})
        assert self._cmd()._passes_filters(feature, {"status": "RETIRED"}) is False

    def test_string_int_comparison_uses_str_strip(self):
        # Feature returns int 5, schema specifies string "5" -- should compare equal.
        feature = _FakeFeature({"count": 5})
        assert self._cmd()._passes_filters(feature, {"count": "5"}) is True

    def test_whitespace_in_value_is_stripped(self):
        feature = _FakeFeature({"status": "  ACTIVE  "})
        assert self._cmd()._passes_filters(feature, {"status": "ACTIVE"}) is True


class TestApplyFieldSpec:
    """Cover Command._apply_field_spec pipeline: null -> regex -> map -> transform -> format."""

    def _cmd(self):
        return Command()

    def test_non_dict_spec_returns_value_unchanged(self):
        assert self._cmd()._apply_field_spec("anything", "not_a_dict") == "anything"

    def test_null_values_short_circuits_to_none(self):
        spec = {"null_values": [0, "N/A"], "transform": "to_int"}
        # Even with a transform queued, null match returns None immediately.
        assert self._cmd()._apply_field_spec("N/A", spec) is None

    def test_regex_extracts_default_group(self):
        spec = {"regex": r"^POLE-(\d+)$"}
        assert self._cmd()._apply_field_spec("POLE-42", spec) == "42"

    def test_regex_uses_explicit_group(self):
        spec = {"regex": r"^(\w+)-(\d+)$", "regex_group": 2}
        assert self._cmd()._apply_field_spec("POLE-42", spec) == "42"

    def test_regex_no_match_returns_default(self):
        spec = {"regex": r"^POLE-(\d+)$", "default": "unknown"}
        assert self._cmd()._apply_field_spec("MANHOLE-7", spec) == "unknown"

    def test_regex_no_match_no_default_returns_none(self):
        spec = {"regex": r"^POLE-(\d+)$"}
        assert self._cmd()._apply_field_spec("MANHOLE-7", spec) is None

    def test_map_hit_returns_mapped_value(self):
        spec = {"map": {"A": "active", "R": "retired"}}
        assert self._cmd()._apply_field_spec("A", spec) == "active"

    def test_map_miss_returns_default(self):
        spec = {"map": {"A": "active"}, "default": "planned"}
        assert self._cmd()._apply_field_spec("ZZ", spec) == "planned"

    def test_map_strips_whitespace_on_key(self):
        spec = {"map": {"A": "active"}}
        assert self._cmd()._apply_field_spec("  A  ", spec) == "active"

    def test_transform_invokes_lambda(self):
        spec = {"transform": "to_int"}
        assert self._cmd()._apply_field_spec("123", spec) == 123

    def test_transform_unknown_raises(self):
        from django.core.management.base import CommandError

        spec = {"transform": "does_not_exist"}
        with pytest.raises(CommandError):
            self._cmd()._apply_field_spec("x", spec)

    def test_format_template_applies(self):
        spec = {"format": "PREFIX-{value}"}
        assert self._cmd()._apply_field_spec("42", spec) == "PREFIX-42"

    def test_format_falls_back_to_str_on_error(self):
        # KeyError path: template references missing placeholder.
        spec = {"format": "{missing}"}
        assert self._cmd()._apply_field_spec(99, spec) == "99"

    def test_regex_then_map_chain(self):
        # The pipeline runs in order; regex output feeds map lookup.
        spec = {
            "regex": r"^(\w+)-",
            "map": {"POLE": "structure", "MH": "manhole"},
        }
        assert self._cmd()._apply_field_spec("POLE-42", spec) == "structure"

    def test_regex_then_transform_chain(self):
        spec = {"regex": r"(\d+)", "transform": "to_int"}
        assert self._cmd()._apply_field_spec("count=37", spec) == 37


class TestLoadSchema:
    """Cover Command._load_schema: YAML file loading with error wrapping."""

    def _cmd(self):
        return Command()

    def test_loads_valid_yaml(self, tmp_path):
        schema_path = tmp_path / "schema.yaml"
        schema_path.write_text("model: structure\ngeometry_field: location\n")
        loaded = self._cmd()._load_schema(str(schema_path))
        assert loaded == {"model": "structure", "geometry_field": "location"}

    def test_missing_file_raises_command_error(self, tmp_path):
        from django.core.management.base import CommandError

        missing = tmp_path / "does_not_exist.yaml"
        with pytest.raises(CommandError, match="Schema file not found"):
            self._cmd()._load_schema(str(missing))

    def test_invalid_yaml_raises_command_error(self, tmp_path):
        from django.core.management.base import CommandError

        schema_path = tmp_path / "broken.yaml"
        # Unbalanced bracket: PyYAML's parser raises YAMLError on this.
        schema_path.write_text("model: [unterminated\n")
        with pytest.raises(CommandError, match="Invalid YAML"):
            self._cmd()._load_schema(str(schema_path))

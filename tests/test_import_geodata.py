from netbox_pathways.management.commands.import_geodata import _matches_null_value


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

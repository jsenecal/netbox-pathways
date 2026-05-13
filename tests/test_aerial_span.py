"""Tests for AerialSpan model -- plugin-owned behavior only."""

import pytest
from django.contrib.gis.geos import LineString

from netbox_pathways.geo import get_srid
from netbox_pathways.models import AerialSpan


def _make_span(**kwargs):
    """Build an unsaved AerialSpan with a valid path; tests don't need to persist."""
    return AerialSpan(
        label=kwargs.pop("label", "test-span"),
        path=LineString([(0.0, 0.0), (0.001, 0.001)], srid=get_srid()),
        **kwargs,
    )


@pytest.mark.parametrize(
    "start, end, expected",
    [
        (8.0, 10.0, 9.0),
        (7.5, 7.5, 7.5),
        (5.0, None, 5.0),
        (None, 12.0, 12.0),
        (None, None, None),
    ],
)
def test_attachment_height_property_returns_mean_with_fallback(start, end, expected):
    span = _make_span(start_attachment_height=start, end_attachment_height=end)
    assert span.attachment_height == expected

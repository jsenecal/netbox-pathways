"""Regression tests for PathwaysMapWidget rendering.

Django 6.0 changed BaseGeometryWidget.get_context so it no longer exposes the
top-level ``id``, ``name`` and ``geom_type`` context variables that the widget
template relies on (they moved under ``widget``). Without compensation the
hidden input renders with an empty ``name`` (so no geometry is submitted) and
the map container renders with an empty ``data-field-id`` (so the JS bails and
no map appears). See issue #52.
"""

from netbox_pathways.forms import PathwaysMapWidget


def _render(widget):
    return widget.render("location", None, attrs={"id": "id_location"})


def test_hidden_input_keeps_field_name():
    """The hidden geometry input must carry name="location" so the form submits a value."""
    html = _render(PathwaysMapWidget(geom_type="Geometry"))
    assert 'name="location"' in html
    assert 'name=""' not in html


def test_map_container_has_field_id():
    """The map container needs a non-empty data-field-id for the JS to initialize."""
    html = _render(PathwaysMapWidget(geom_type="Geometry"))
    assert 'data-field-id="id_location"' in html
    assert 'data-field-id=""' not in html


def test_geom_type_is_exposed():
    """The configured geometry type must reach the template's data-geom-type."""
    assert 'data-geom-type="Geometry"' in _render(PathwaysMapWidget(geom_type="Geometry"))
    assert 'data-geom-type="LineString"' in _render(PathwaysMapWidget(geom_type="LineString"))

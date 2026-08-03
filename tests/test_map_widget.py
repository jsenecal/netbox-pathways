"""Regression tests for PathwaysMapWidget rendering.

Django 6.0 changed BaseGeometryWidget.get_context so it no longer exposes the
top-level ``id``, ``name`` and ``geom_type`` context variables that the widget
template relies on (they moved under ``widget``). Without compensation the
hidden input renders with an empty ``name`` (so no geometry is submitted) and
the map container renders with an empty ``data-field-id`` (so the JS bails and
no map appears). See issue #52.
"""

from netbox_pathways.forms import PathwaysMapWidget, StructureForm
from netbox_pathways.models import Structure


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


def test_ref_exclude_pk_reaches_the_map_container():
    """The nearby-structures layer reads the id to skip off the map container."""
    widget = PathwaysMapWidget(geom_type="Geometry")
    assert "data-ref-exclude-id" not in _render(widget)

    widget.ref_exclude_pk = 42
    assert 'data-ref-exclude-id="42"' in _render(widget)


def test_structure_form_excludes_the_edited_structure(db):
    """Editing a structure hides its own reference marker; adding one has nothing to hide."""
    assert StructureForm(instance=Structure(pk=42)).fields["geometry"].widget.ref_exclude_pk == 42
    assert StructureForm().fields["geometry"].widget.ref_exclude_pk is None

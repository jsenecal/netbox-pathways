"""Regression tests for issue #58: bulk import coverage.

NetBox's ``BulkImport`` object action (the Import button on list views)
resolves the URL name ``plugins:netbox_pathways:<model>_bulk_import``. The
plugin previously registered its import views under ``<model>_import`` --
so every list-view Import button was a dead link -- and omitted import
views entirely for six models. ``ConduitBankImportForm`` was also missing
the ``length`` field.
"""

import pytest
from dcim.models import Location, Site
from django.contrib.gis.geos import Point
from django.urls import reverse
from utilities.views import get_viewname

from netbox_pathways import forms, models
from netbox_pathways.geo import get_srid
from netbox_pathways.navigation import menu

SRID = get_srid()

IMPORTABLE_MODELS = [
    models.Structure,
    models.Conduit,
    models.AerialSpan,
    models.DirectBuried,
    models.Innerduct,
    models.ConduitBank,
    models.ConduitJunction,
    models.CableSegment,
    models.PlannedRoute,
    models.SiteGeometry,
    models.CircuitGeometry,
]


@pytest.mark.parametrize("model", IMPORTABLE_MODELS, ids=lambda m: m._meta.model_name)
def test_bulk_import_url_resolves(model):
    """Each importable model registers the URL name the Import button reverses."""
    url = reverse(get_viewname(model, "bulk_import"))
    assert url.endswith("/import/")


def test_navigation_button_links_resolve():
    """Every menu item and button in the plugin menu points at a real URL name."""
    for group in menu.groups:
        for item in group.items:
            reverse(item.link)
            for button in item.buttons:
                reverse(button.link)


def test_navigation_has_import_button_per_importable_model():
    """Each importable model's menu item carries an Import button."""
    buttons = set()
    for group in menu.groups:
        for item in group.items:
            for button in item.buttons:
                buttons.add(button.link)
    missing = [
        model._meta.model_name for model in IMPORTABLE_MODELS if get_viewname(model, "bulk_import") not in buttons
    ]
    assert not missing


@pytest.fixture
def structures(db):
    # Import geometry is parsed as EPSG:4326 then reprojected to the storage
    # SRID, so anchor the structures at reprojected 4326 points to match.
    s1 = models.Structure.objects.create(
        name="Import test A",
        structure_type="manhole",
        location=Point(-73.5, 45.5, srid=4326).transform(SRID, clone=True),
    )
    s2 = models.Structure.objects.create(
        name="Import test B",
        structure_type="manhole",
        location=Point(-73.501, 45.5, srid=4326).transform(SRID, clone=True),
    )
    return s1, s2


@pytest.mark.django_db
def test_conduitbank_import_form_accepts_length(structures):
    """`length` is importable on conduit banks, matching the GUI add form."""
    s1, s2 = structures
    form = forms.ConduitBankImportForm(
        data={
            "label": "CB import",
            "start_structure": s1.name,
            "end_structure": s2.name,
            "path": "LINESTRING(-73.5 45.5, -73.501 45.5)",
            "length": "123.4",
        }
    )
    assert form.is_valid(), form.errors
    assert form.instance.length == 123.4


@pytest.mark.django_db
def test_directburied_import_form_accepts_location_endpoints():
    """Indoor (location-to-location, pathless) rows import cleanly."""
    site = Site.objects.create(name="Import Site", slug="import-site")
    loc_a = Location.objects.create(site=site, name="Import Room A", slug="import-room-a")
    loc_b = Location.objects.create(site=site, name="Import Room B", slug="import-room-b")
    form = forms.DirectBuriedImportForm(
        data={
            "label": "DB import",
            "start_location": loc_a.name,
            "end_location": loc_b.name,
            "length": "12",
        }
    )
    assert form.is_valid(), form.errors
    assert form.instance.start_location == loc_a
    assert form.instance.end_location == loc_b

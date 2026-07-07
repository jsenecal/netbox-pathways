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


# Model fields deliberately absent from CSV import, with the reason.
IMPORT_FIELD_EXCLUSIONS = {
    models.PlannedRoute: {
        "pathway_ids",  # computed by the route-planning engine
        "constraints",  # computed by the route-planning engine
        "parent",  # set by route-split operations, never by hand
    },
}

# Framework plumbing present on every NetBoxModel; never CSV columns.
NON_IMPORT_FIELDS = {"id", "created", "last_updated", "custom_field_data", "tags"}


def _import_forms():
    return [
        obj
        for name, obj in vars(forms).items()
        if isinstance(obj, type)
        and name.endswith("ImportForm")
        and obj.__module__ == forms.__name__
        and hasattr(obj, "Meta")
    ]


@pytest.mark.parametrize("form_cls", _import_forms(), ids=lambda f: f.__name__)
def test_import_form_covers_all_editable_model_fields(form_cls):
    """Every editable concrete model field is importable unless excluded above.

    Guards against model/import-form drift like issue #58's missing
    conduit_bank and bank_position columns: a new model field must either
    appear in the import form or be added to IMPORT_FIELD_EXCLUSIONS with a
    reason.
    """
    model = form_cls.Meta.model
    declared = set(form_cls.Meta.fields) | set(form_cls.base_fields)
    excluded = NON_IMPORT_FIELDS | IMPORT_FIELD_EXCLUSIONS.get(model, set())
    missing = [
        f.name
        for f in model._meta.get_fields()
        if getattr(f, "concrete", False)
        and f.editable
        and not f.auto_created
        and f.name not in excluded
        and f.name not in declared
    ]
    assert not missing, f"{form_cls.__name__} is missing importable columns: {missing}"


@pytest.mark.django_db
def test_conduit_import_form_accepts_bank_and_position(structures):
    """Conduit rows can carry bank membership by bank label (issue #58 follow-up)."""
    s1, s2 = structures
    bank = models.ConduitBank.objects.create(label="CB58", start_structure=s1, end_structure=s2)
    form = forms.ConduitImportForm(
        data={
            "label": "C58",
            "start_structure": s1.name,
            "end_structure": s2.name,
            "conduit_bank": bank.label,
            "bank_position": "A1",
        }
    )
    assert form.is_valid(), form.errors
    assert form.instance.conduit_bank == bank
    assert form.instance.bank_position == "A1"

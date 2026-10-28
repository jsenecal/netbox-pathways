"""The single pathway form shows the fields of the chosen pathway type."""

import pytest

from netbox_pathways.forms import PathwayForm


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("pathway_type", "present", "absent"),
    [
        ("aerial", {"sag", "aerial_type"}, {"size", "material", "parent"}),
        ("innerduct", {"size", "color", "position", "parent"}, {"sag", "material"}),
        ("submarine", set(), {"parent", "size", "sag", "material"}),
        ("conduit", {"material", "start_junction", "parent", "position"}, {"size", "configuration"}),
    ],
)
def test_form_fields_follow_type(pathway_type, present, absent):
    fields = set(PathwayForm(initial={"pathway_type": pathway_type}).fields)
    assert present <= fields
    assert not absent & fields


@pytest.mark.django_db
def test_form_type_change_rerenders_with_new_fields():
    """A bound form follows the submitted type, not the instance's."""
    form = PathwayForm(data={"pathway_type": "conduit"})
    assert "material" in form.fields
    assert "sag" not in form.fields


@pytest.mark.django_db
def test_form_fieldsets_list_only_present_fields():
    form = PathwayForm(initial={"pathway_type": "innerduct"})
    rendered = {item for fieldset in form.fieldsets for item in fieldset.items}
    assert {"size", "color", "position", "parent"} <= rendered
    assert rendered - {"tags"} <= set(form.fields)


@pytest.mark.django_db
def test_parent_selector_limited_to_allowed_parent_types():
    form = PathwayForm(initial={"pathway_type": "innerduct"})
    params = form.fields["parent"].widget.attrs["data-static-params"]
    for parent_type in ("conduit", "innerduct", "direct_buried", "tray"):
        assert parent_type in params
    assert "aerial" not in params


@pytest.mark.django_db
def test_form_without_a_type_shows_no_type_specific_fields():
    fields = set(PathwayForm().fields)
    assert "pathway_type" in fields
    assert not {"parent", "material", "size", "sag"} & fields

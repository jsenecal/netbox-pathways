"""Retiring the five pathway subtype content types during the flatten upgrade.

The helpers run against the live app registry here; the legacy content types
no longer have models, so the fixture recreates their rows the way an
upgraded 0.4.x database still holds them.
"""

from uuid import uuid4

import django.apps
import pytest
from core.models import ObjectChange, ObjectType
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from extras.models import CustomField, ExportTemplate, JournalEntry, Tag, TaggedItem
from users.models import ObjectPermission

from netbox_pathways.models import Pathway
from netbox_pathways.upgrade import (
    LEGACY_SUBTYPES,
    UntranslatableConstraint,
    convert_object_permissions,
    relax_custom_fields,
    repoint_content_type_references,
    retire_subtype_content_types,
    rewrite_constraints,
)

APPS = django.apps.apps


@pytest.fixture
def legacy(db):
    """{legacy model name: ObjectType} for the five former subtypes."""
    types = {}
    for model in LEGACY_SUBTYPES:
        types[model] = ObjectType.objects.filter(app_label="netbox_pathways", model=model).first()
        if types[model] is None:
            types[model] = ObjectType.objects.create(app_label="netbox_pathways", model=model, public=True, features=[])
    yield types
    ContentType.objects.clear_cache()


@pytest.fixture
def pathway_ct(db):
    return ObjectType.objects.get_for_model(Pathway)


@pytest.fixture
def pathways(db):
    """One conduit and one aerial span, inserted without validation."""
    conduit, span = Pathway.objects.bulk_create(
        [Pathway(pathway_type="conduit", label="CT-C"), Pathway(pathway_type="aerial", label="CT-A")]
    )
    return conduit, span


def _ids(legacy):
    return [ct.pk for ct in legacy.values()]


def _pks(manager):
    return sorted(manager.values_list("pk", flat=True))


def _permission(name, object_types, constraints=None, actions=("view",)):
    perm = ObjectPermission.objects.create(name=name, actions=list(actions), constraints=constraints)
    perm.object_types.set(object_types)
    return perm


def test_rewrite_constraints_renames_and_scopes():
    assert rewrite_constraints({"conduit_bank__label": "B1"}, ["conduit"]) == {
        "parent__label": "B1",
        "pathway_type__in": ["conduit"],
    }
    assert rewrite_constraints(
        [{"parent_conduit": 4}, {"bank_position": "A1", "path__isnull": False}, {"pathway_ptr_id__in": [1]}],
        ["innerduct"],
    ) == [
        {"parent": 4, "pathway_type__in": ["innerduct"]},
        {"position": "A1", "geometry__isnull": False, "pathway_type__in": ["innerduct"]},
        {"id__in": [1], "pathway_type__in": ["innerduct"]},
    ]
    assert rewrite_constraints(None, ["conduit", "aerial"]) == {"pathway_type__in": ["conduit", "aerial"]}
    assert rewrite_constraints([], ["aerial"]) == {"pathway_type__in": ["aerial"]}
    # The parent link is the row itself on the flattened model.
    assert rewrite_constraints({"pathway_ptr__label": "x", "pk__in": [2]}, ["aerial"]) == {
        "label": "x",
        "pk__in": [2],
        "pathway_type__in": ["aerial"],
    }
    # A legacy name reached through a relation back to a pathway is renamed too.
    assert rewrite_constraints({"parent_conduit__conduit_bank__label": "B1"}, ["innerduct"]) == {
        "parent__parent__label": "B1",
        "pathway_type__in": ["innerduct"],
    }


def test_rewrite_constraints_narrows_an_existing_type_filter():
    """A constraint that already filtered on type keeps only the types both allow."""
    assert rewrite_constraints({"pathway_type__in": ["conduit", "aerial"]}, ["conduit"]) == {
        "pathway_type__in": ["conduit"]
    }


@pytest.mark.parametrize(
    "constraints",
    [{"nonexistent": 1}, {"label__nonexistent": 1}, [{"tenant__bogus__x": 1}], {"pathway_type__in": "conduit"}],
)
def test_rewrite_constraints_rejects_unknown_field(constraints):
    with pytest.raises(UntranslatableConstraint):
        rewrite_constraints(constraints, ["conduit"])


@pytest.mark.django_db
def test_view_conduit_permission_scopes_to_conduits(legacy, pathway_ct, pathways):
    """Review focus: a user who could view only conduits still sees only conduits."""
    conduit, span = pathways
    user = get_user_model().objects.create_user(username="ct-conduit-viewer")
    perm = _permission("View conduits", [legacy["conduit"]])
    perm.users.add(user)

    convert_object_permissions(APPS, _ids(legacy), pathway_ct.pk)

    user = get_user_model().objects.get(pk=user.pk)
    visible = set(Pathway.objects.restrict(user, "view").values_list("pk", flat=True))
    assert conduit.pk in visible
    assert span.pk not in visible
    assert not ObjectPermission.objects.filter(pk=perm.pk).exists()
    (converted,) = ObjectPermission.objects.filter(name="View conduits (pathways)")
    assert _pks(converted.object_types) == [pathway_ct.pk]
    assert converted.constraints == {"pathway_type__in": ["conduit"]}


@pytest.mark.django_db
def test_permission_with_other_types_keeps_them(legacy, pathway_ct):
    site_ct = ContentType.objects.get(app_label="dcim", model="site")
    group = get_user_model()._meta.get_field("groups").related_model.objects.create(name="ct-group")
    perm = _permission(
        "Edit sites and conduits",
        [legacy["conduit"], legacy["innerduct"], site_ct],
        constraints={"tenant__slug": "t1"},
        actions=("view", "change"),
    )
    perm.groups.add(group)

    convert_object_permissions(APPS, _ids(legacy), pathway_ct.pk)

    perm.refresh_from_db()
    assert _pks(perm.object_types) == [site_ct.pk]
    assert perm.constraints == {"tenant__slug": "t1"}
    converted = ObjectPermission.objects.get(name="Edit sites and conduits (pathways)")
    assert converted.actions == ["view", "change"]
    assert list(converted.groups.all()) == [group]
    assert converted.constraints == {"tenant__slug": "t1", "pathway_type__in": ["conduit", "innerduct"]}


@pytest.mark.django_db
def test_untranslatable_permission_aborts_before_writing(legacy, pathway_ct):
    fine = _permission("Fine", [legacy["conduit"]])
    _permission("Broken A", [legacy["aerialspan"]], constraints={"wind_speed": 3})
    _permission("Broken B", [legacy["innerduct"]], constraints=[{"label": "x"}, {"duct_colour": "red"}])

    with pytest.raises(UntranslatableConstraint) as excinfo:
        convert_object_permissions(APPS, _ids(legacy), pathway_ct.pk)

    assert "Broken A" in str(excinfo.value)
    assert "Broken B" in str(excinfo.value)
    assert _pks(ObjectPermission.objects.get(pk=fine.pk).object_types) == [legacy["conduit"].pk]
    assert not ObjectPermission.objects.filter(name__endswith="(pathways)").exists()


@pytest.mark.django_db
def test_repoint_moves_tags_journal_and_changelog(legacy, pathway_ct, pathways):
    conduit, _ = pathways
    legacy_ct = legacy["conduit"]
    tag = Tag.objects.create(name="ct-tag", slug="ct-tag")
    tagged = TaggedItem.objects.create(tag=tag, content_type_id=legacy_ct.pk, object_id=conduit.pk)
    journal = JournalEntry.objects.create(
        assigned_object_type_id=legacy_ct.pk, assigned_object_id=conduit.pk, comments="note"
    )
    change = ObjectChange.objects.create(
        changed_object_type_id=legacy_ct.pk,
        changed_object_id=conduit.pk,
        action="create",
        object_repr="CT-C",
        user_name="upgrade",
        request_id=uuid4(),
    )
    template = ExportTemplate.objects.create(name="ct-export", template_code="x")
    template.object_types.set([legacy["conduit"], legacy["aerialspan"]])

    repoint_content_type_references(APPS, _ids(legacy), pathway_ct.pk)

    for row, field in ((tagged, "content_type_id"), (journal, "assigned_object_type_id")):
        row.refresh_from_db()
        assert getattr(row, field) == pathway_ct.pk
    change.refresh_from_db()
    assert change.changed_object_type_id == pathway_ct.pk
    assert _pks(template.object_types) == [pathway_ct.pk]


@pytest.mark.django_db
def test_repoint_drops_a_duplicate_of_an_existing_pathway_reference(legacy, pathway_ct, pathways):
    """A bookmark on both the pathway and its former subtype collapses to one row."""
    conduit, _ = pathways
    bookmark_model = APPS.get_model("extras", "Bookmark")
    user = get_user_model().objects.create_user(username="ct-bookmarker")
    bookmark_model.objects.create(object_type_id=pathway_ct.pk, object_id=conduit.pk, user=user)
    bookmark_model.objects.create(object_type_id=legacy["conduit"].pk, object_id=conduit.pk, user=user)

    repoint_content_type_references(APPS, _ids(legacy), pathway_ct.pk)

    assert bookmark_model.objects.filter(object_id=conduit.pk, user=user).count() == 1
    assert bookmark_model.objects.get(object_id=conduit.pk, user=user).object_type_id == pathway_ct.pk


@pytest.mark.django_db
def test_relax_custom_fields(legacy, pathway_ct, pathways):
    conduit, span = pathways
    unique_cf = CustomField.objects.create(name="ct_asset", type="text", unique=True)
    unique_cf.object_types.set([legacy["conduit"], legacy["aerialspan"]])
    distinct_cf = CustomField.objects.create(name="ct_serial", type="text", unique=True)
    distinct_cf.object_types.set([legacy["conduit"], legacy["aerialspan"]])
    Pathway.objects.filter(pk=conduit.pk).update(custom_field_data={"ct_asset": "X1", "ct_serial": "S1"})
    Pathway.objects.filter(pk=span.pk).update(custom_field_data={"ct_asset": "X1", "ct_serial": ""})
    partial_cf = CustomField.objects.create(name="ct_sag_class", type="text", required=True)
    partial_cf.object_types.set([legacy["aerialspan"]])
    full_cf = CustomField.objects.create(name="ct_owner", type="text", required=True)
    full_cf.object_types.set(list(legacy.values()))
    base_cf = CustomField.objects.create(name="ct_base", type="text", required=True)
    base_cf.object_types.set([legacy["conduit"], pathway_ct])

    log = relax_custom_fields(APPS, _ids(legacy), pathway_ct.pk)

    for cf in (unique_cf, distinct_cf, partial_cf, full_cf, base_cf):
        cf.refresh_from_db()
    assert not unique_cf.unique
    assert distinct_cf.unique
    assert not partial_cf.required
    assert full_cf.required
    assert base_cf.required
    assert len(log) == 2
    assert any("ct_asset" in line and "unique" in line for line in log)
    assert any("ct_sag_class" in line and "required" in line for line in log)


@pytest.mark.django_db
def test_retire_subtype_content_types(legacy, pathway_ct, pathways, capsys):
    conduit, span = pathways
    user = get_user_model().objects.create_user(username="ct-retire")
    _permission("Retire view", [legacy["aerialspan"]]).users.add(user)
    tag = Tag.objects.create(name="ct-retire", slug="ct-retire")
    TaggedItem.objects.create(tag=tag, content_type_id=legacy["aerialspan"].pk, object_id=span.pk)
    cf = CustomField.objects.create(name="ct_retire", type="text", required=True)
    cf.object_types.set([legacy["conduit"]])

    retire_subtype_content_types(APPS, None)

    assert not ContentType.objects.filter(app_label="netbox_pathways", model__in=list(LEGACY_SUBTYPES)).exists()
    assert TaggedItem.objects.get(tag=tag).content_type_id == pathway_ct.pk
    cf.refresh_from_db()
    assert not cf.required
    assert _pks(cf.object_types) == [pathway_ct.pk]
    user = get_user_model().objects.get(pk=user.pk)
    assert set(Pathway.objects.restrict(user, "view").values_list("pk", flat=True)) == {span.pk}
    assert "ct_retire" in capsys.readouterr().out


@pytest.mark.django_db
def test_retire_without_legacy_types_is_a_no_op(pathway_ct):
    ContentType.objects.filter(app_label="netbox_pathways", model__in=list(LEGACY_SUBTYPES)).delete()
    ContentType.objects.clear_cache()
    retire_subtype_content_types(APPS, None)
    assert ContentType.objects.filter(pk=pathway_ct.pk).exists()

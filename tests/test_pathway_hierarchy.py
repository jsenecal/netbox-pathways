"""The single-table pathway hierarchy: containment, ltree paths, map containers.

Covers the rules Pathway.clean(), save() and the database constraints own
after the subtype tables were flattened (issues #103, #166, #172, #173, #177).
"""

import pytest
from django.apps import apps
from django.contrib.gis.geos import LineString
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from tenancy.models import Tenant

from netbox_pathways.models import ConduitJunction, Pathway
from tests.helpers import SRID, make_pole


@pytest.fixture
def ends(db):
    return make_pole("PH-S1", 0, 0), make_pole("PH-S2", 100, 0)


def build(pathway_type, ends, parent=None, **kwargs):
    """A saved, validated pathway; top-level ones run between `ends`."""
    if parent is None:
        kwargs.setdefault("start_structure", ends[0])
        kwargs.setdefault("end_structure", ends[1])
        kwargs.setdefault("geometry", LineString((0, 0), (100, 0), srid=SRID))
    pathway = Pathway(pathway_type=pathway_type, parent=parent, **kwargs)
    pathway.full_clean()
    pathway.save()
    return pathway


def build_valid(pathway_type, ends):
    """A saved pathway of `pathway_type`, with whatever parent it needs."""
    if pathway_type == "innerduct":
        return build("innerduct", ends, parent=build("conduit", ends))
    return build(pathway_type, ends)


def test_no_model_uses_multi_table_inheritance():
    """netbox-branching cannot provision MTI child tables (issue #103)."""
    offenders = [m.__name__ for m in apps.get_app_config("netbox_pathways").get_models() if m._meta.parents]
    assert offenders == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("parent_type", "child_type"),
    [
        ("conduit_bank", "conduit"),
        ("raceway", "conduit"),
        ("raceway", "tray"),
        ("tray", "innerduct"),
        ("conduit", "innerduct"),
        ("innerduct", "innerduct"),
        ("direct_buried", "innerduct"),
    ],
)
def test_containment_allows(ends, parent_type, child_type):
    parent = build_valid(parent_type, ends)
    Pathway(pathway_type=child_type, parent=parent).full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("parent_type", "child_type"),
    [
        ("tray", "conduit"),
        ("conduit", "tray"),
        (None, "innerduct"),
        ("conduit_bank", "aerial"),
        ("aerial", "innerduct"),
        ("conduit_bank", "conduit_bank"),
    ],
)
def test_containment_rejects(ends, parent_type, child_type):
    parent = build_valid(parent_type, ends) if parent_type else None
    child = Pathway(
        pathway_type=child_type,
        parent=parent,
        start_structure=ends[0],
        end_structure=ends[1],
        geometry=LineString((0, 0), (100, 0), srid=SRID),
    )
    with pytest.raises(ValidationError) as excinfo:
        child.full_clean()
    assert "parent" in excinfo.value.message_dict


@pytest.mark.django_db
def test_type_change_rejected_when_children_disallowed(ends):
    conduit = build("conduit", ends)
    build("innerduct", ends, parent=conduit)
    conduit.pathway_type = "aerial"
    with pytest.raises(ValidationError) as excinfo:
        conduit.full_clean()
    assert "pathway_type" in excinfo.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["trunk_conduit", "branch_conduit"])
def test_type_change_rejected_when_conduit_holds_a_junction(ends, role):
    """A junction's trunk and branch must stay conduits; retyping either is refused."""
    trunk = build("conduit", ends, label="JT")
    branch = build("conduit", ends, label="JB")
    ConduitJunction.objects.create(
        trunk_conduit=trunk, branch_conduit=branch, towards_structure=ends[1], position_on_trunk=0.5
    )
    pathway = {"trunk_conduit": trunk, "branch_conduit": branch}[role]
    pathway.pathway_type = "direct_buried"
    with pytest.raises(ValidationError) as excinfo:
        pathway.full_clean()
    assert "pathway_type" in excinfo.value.message_dict


@pytest.mark.django_db
def test_reparent_rewrites_subtree_path(ends):
    """Moving a pathway re-paths its subtree; stale instances still resolve correctly."""
    b1 = build("conduit_bank", ends, label="B1")
    b2 = build("conduit_bank", ends, label="B2")
    conduit = build("conduit", ends, parent=b1)
    duct = build("innerduct", ends, parent=conduit)
    stale = Pathway.objects.get(pk=duct.pk)

    conduit.parent = b2
    conduit.save()

    duct.refresh_from_db()
    assert str(duct.path).split(".")[0] == str(b2.path)
    assert duct.map_container == b2
    assert stale.map_container == b2


@pytest.mark.django_db
def test_map_container(ends):
    bank = build("conduit_bank", ends)
    standalone = build("conduit", ends)
    banked = build("conduit", ends, parent=bank)
    duct_in_bank = build("innerduct", ends, parent=banked)
    buried = build("direct_buried", ends)
    duct_in_buried = build("innerduct", ends, parent=buried)
    raceway = build("raceway", ends)
    in_raceway = build("conduit", ends, parent=raceway)
    tray = build("tray", ends)

    assert standalone.map_container == standalone
    assert banked.map_container == bank
    assert duct_in_bank.map_container == bank
    assert duct_in_buried.map_container == buried
    assert in_raceway.map_container is None
    assert tray.map_container is None
    assert set(Pathway.objects.map_containers()) == {bank, standalone, buried}


@pytest.mark.django_db
def test_map_select_id(ends):
    bank = build("conduit_bank", ends)
    assert bank.map_select_id == f"conduit_bank-{bank.pk}"


@pytest.mark.django_db
def test_delete_container_with_children_is_protected(ends):
    bank = build("conduit_bank", ends)
    build("conduit", ends, parent=bank)
    with pytest.raises(ProtectedError):
        bank.delete()
    assert Pathway.objects.filter(pk=bank.pk).exists()


@pytest.mark.django_db
def test_delete_leaf_succeeds(ends):
    bank = build("conduit_bank", ends)
    conduit = build("conduit", ends, parent=bank)
    conduit.delete()
    assert not Pathway.objects.filter(pk=conduit.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("parent_type", "child_type"),
    [("conduit_bank", "conduit"), ("raceway", "conduit"), ("conduit", "innerduct")],
)
def test_child_inherits_unset_endpoints_from_parent(ends, parent_type, child_type):
    parent = build(parent_type, ends)
    child = build(child_type, ends, parent=parent)
    child.refresh_from_db()
    assert (child.start_structure, child.end_structure) == ends


@pytest.mark.django_db
def test_child_keeps_its_own_endpoint(ends):
    other = make_pole("PH-S3", 50, 0)
    bank = build("conduit_bank", ends)
    conduit = build("conduit", ends, parent=bank, start_structure=other)
    assert (conduit.start_structure, conduit.end_structure) == (other, ends[1])


@pytest.mark.django_db
def test_effective_tenant_walks_ancestors(ends):
    """Any chain, not only bank -> conduit -> innerduct; the nearest tenant wins."""
    owner = Tenant.objects.create(name="PH Owner", slug="ph-owner")
    middle = Tenant.objects.create(name="PH Middle", slug="ph-middle")
    raceway = build("raceway", ends, tenant=owner)
    tray = build("tray", ends, parent=raceway)
    duct = build("innerduct", ends, parent=tray)
    nested = build("innerduct", ends, parent=duct)

    assert nested.effective_tenant == owner
    duct.tenant = middle
    duct.save()
    assert nested.effective_tenant == middle


@pytest.mark.django_db
def test_effective_tenant_of_a_list_costs_no_queries_per_access(ends, django_assert_num_queries):
    """Tables read effective_tenant several times per row; no read may re-query."""
    owner = Tenant.objects.create(name="PH Bank Owner", slug="ph-bank-owner")
    bank = build("conduit_bank", ends, tenant=owner)
    raceway = build("raceway", ends, tenant=owner)
    tray = build("tray", ends, parent=raceway)
    for n in range(3):
        build("conduit", ends, parent=bank, position=str(n))
        build("innerduct", ends, parent=tray)

    children = list(Pathway.objects.filter(parent=bank).select_related("parent__tenant"))
    with django_assert_num_queries(0):
        assert [c.effective_tenant for c in children for _ in range(3)] == [owner] * 9

    # A chain deeper than what was loaded reads the rest once per row.
    ducts = list(Pathway.objects.filter(parent=tray))
    with django_assert_num_queries(3):
        assert [d.effective_tenant for d in ducts for _ in range(3)] == [owner] * 9


@pytest.mark.django_db
def test_inapplicable_fields_cleared_on_save(ends):
    conduit = build("conduit", ends)
    duct = Pathway(pathway_type="innerduct", parent=conduit, material="pvc", sag=1.5, warning_tape=True)
    duct.save()
    duct.refresh_from_db()
    assert (duct.material, duct.sag, duct.warning_tape) == ("", None, False)


@pytest.mark.django_db
def test_banked_conduit_position_unique(ends):
    bank = build("conduit_bank", ends)
    build("conduit", ends, parent=bank, position="A1")
    with pytest.raises(ValidationError):
        build("conduit", ends, parent=bank, position="A1")


@pytest.mark.django_db
def test_innerduct_position_not_unique(ends):
    conduit = build("conduit", ends)
    build("innerduct", ends, parent=conduit, position="1")
    build("innerduct", ends, parent=conduit, position="1")
    assert conduit.children.count() == 2


@pytest.mark.django_db
def test_route_geometry_falls_back_to_the_nearest_ancestor(ends, django_assert_num_queries):
    """A pathway with no geometry of its own follows the nearest ancestor that has one."""
    bank = build("conduit_bank", ends)
    banked = build("conduit", ends, parent=bank)
    duct = build("innerduct", ends, parent=banked)
    own = LineString((0, 0), (50, 10), (100, 0), srid=SRID)
    routed = build("conduit", ends, parent=bank, geometry=own)
    duct_in_routed = build("innerduct", ends, parent=routed)

    assert bank.route_geometry.equals(bank.geometry)
    assert duct.route_geometry.equals(bank.geometry)
    assert duct_in_routed.route_geometry.equals(own)

    annotated = {p.pk: p for p in Pathway.objects.with_route_geometry()}
    with django_assert_num_queries(0):
        resolved = {pk: p.route_geometry for pk, p in annotated.items()}
    assert resolved[banked.pk].equals(bank.geometry)
    assert resolved[duct.pk].equals(bank.geometry)
    assert resolved[duct_in_routed.pk].equals(own)


@pytest.mark.django_db
def test_route_geometry_is_none_when_no_ancestor_has_one(db):
    tray = Pathway(pathway_type="tray")
    tray.save()
    duct = Pathway(pathway_type="innerduct", parent=tray)
    duct.save()

    assert duct.route_geometry is None
    assert Pathway.objects.with_route_geometry().get(pk=duct.pk).route_geometry is None


@pytest.mark.django_db
def test_route_geometry_is_looked_up_once_per_parent(ends, django_assert_num_queries):
    bank = build("conduit_bank", ends)
    duct = build("innerduct", ends, parent=build("conduit", ends, parent=bank))
    duct = Pathway.objects.get(pk=duct.pk)

    assert duct.route_geometry.equals(bank.geometry)
    with django_assert_num_queries(0):
        assert duct.route_geometry.equals(bank.geometry)


@pytest.mark.django_db
def test_clean_of_an_unknown_type_reports_only_the_choice(db):
    """An untyped or retired-type row left by the upgrade fails on its type, not on rules it has none of."""
    pathway = Pathway(pathway_type="microduct", label="PH-Unknown")
    with pytest.raises(ValidationError) as excinfo:
        pathway.full_clean()
    assert set(excinfo.value.message_dict) == {"pathway_type"}

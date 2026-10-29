"""The upgrade from the five subtype tables to the single pathway table.

The migration test rebuilds the schema twice (back to the subtype layout,
then forward); run it in its own invocation with --create-db when the
migration chain changes.
"""

import django.apps
import pytest
from core.models import ObjectType
from dcim.models import Cable
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from users.models import ObjectPermission

from netbox_pathways.models import CableSegment, ConduitJunction, Pathway
from netbox_pathways.upgrade import LEGACY_SUBTYPES, delete_microducts, uncopy_subtype_rows
from tests.helpers import SRID

BEFORE_FLATTEN = "0027_rename_pathway_path_geometry"


def test_legacy_subtypes_name_every_former_child_table():
    assert LEGACY_SUBTYPES == {
        "conduitbank": "conduit_bank",
        "conduit": "conduit",
        "aerialspan": "aerial",
        "directburied": "direct_buried",
        "innerduct": "innerduct",
    }


@pytest.mark.django_db
def test_delete_microducts(_disable_routability_signal, capsys):
    (microduct,) = Pathway.objects.bulk_create([Pathway(pathway_type="microduct", label="MD-1")])
    keeper = Pathway.objects.create(pathway_type="raceway", label="RW-1")
    cable = Cable.objects.create(label="MD-Cable")
    segment = CableSegment.objects.create(cable=cable, pathway=microduct, sequence=1)

    assert delete_microducts(django.apps.apps, None) == 1

    assert not Pathway.objects.filter(pk=microduct.pk).exists()
    assert Pathway.objects.filter(pk=keeper.pk).exists()
    segment.refresh_from_db()
    assert segment.pathway_id is None
    assert "1" in capsys.readouterr().out


def _legacy_models(executor):
    state = executor.loader.project_state([("netbox_pathways", BEFORE_FLATTEN)])
    return {
        name: state.apps.get_model("netbox_pathways", name)
        for name in ("structure", "conduitjunction", "pathway", *LEGACY_SUBTYPES)
    }


@pytest.mark.django_db(transaction=True)
def test_copy_subtype_rows(migrate_to, capsys):
    executor = migrate_to(BEFORE_FLATTEN)
    old = _legacy_models(executor)
    pole = old["structure"].objects.create(name="UF-P1", geometry=Point(0, 0, srid=SRID))
    bank = old["conduitbank"].objects.create(
        pathway_type="conduit_bank", label="UF-B", configuration="2x2", total_conduits=4, start_face="north"
    )
    conduit = old["conduit"].objects.create(
        pathway_type="conduit",
        label="UF-C",
        conduit_bank=bank,
        bank_position="A1",
        material="pvc",
        start_structure_id=pole.pk,
    )
    duct = old["innerduct"].objects.create(
        pathway_type="innerduct", label="UF-I", parent_conduit=conduit, size="32mm", color="ff0000", position="2"
    )
    junction = old["conduitjunction"].objects.create(
        trunk_conduit=conduit, branch_conduit=conduit, towards_structure_id=pole.pk, position_on_trunk=0.5
    )
    lateral = old["conduit"].objects.create(pathway_type="conduit", label="UF-L", start_junction=junction)
    span = old["aerialspan"].objects.create(pathway_type="aerial", label="UF-A", aerial_type="lashed", sag=1.5)
    buried = old["directburied"].objects.create(
        pathway_type="direct_buried", label="UF-D", burial_depth=1.2, warning_tape=True
    )

    # Base rows with no child row, as the 0.4.x generic endpoint stored them.
    orphan = old["pathway"].objects.create(pathway_type="innerduct", label="UF-OI")
    bare_conduit = old["pathway"].objects.create(pathway_type="conduit", label="UF-BC")
    untyped = old["pathway"].objects.create(pathway_type="", label="UF-UT")
    # Before the upgrade this permission reached only rows of the conduit table.
    viewer = get_user_model().objects.create_user(username="uf-conduit-viewer")
    perm = ObjectPermission.objects.create(name="UF view conduits", actions=["view"])
    perm.object_types.set([ObjectType.objects.get_or_create(app_label="netbox_pathways", model="conduit")[0]])
    perm.users.add(viewer)

    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes("netbox_pathways"))

    # None is deleted: the bare innerduct and conduit lose only their type, so
    # the parent constraint holds and the converted conduit permission does
    # not widen to them; the blank-typed row already satisfies both.
    bare = [orphan.pk, bare_conduit.pk, untyped.pk]
    survivors = dict(Pathway.objects.filter(pk__in=bare).values_list("label", "pathway_type"))
    assert survivors == {"UF-OI": "", "UF-BC": "", "UF-UT": ""}
    out = capsys.readouterr().out
    assert (
        f"cleared the type of 2 pathway(s) with no subtype row; set a type on each: {orphan.pk}, {bare_conduit.pk}."
        in out
    )
    viewer = get_user_model().objects.get(pk=viewer.pk)
    visible = set(Pathway.objects.restrict(viewer, "view").values_list("pk", flat=True))
    assert visible == {conduit.pk, lateral.pk}
    flat_bank = Pathway.objects.get(pk=bank.pk)
    assert (flat_bank.configuration, flat_bank.total_conduits, flat_bank.start_face) == ("2x2", 4, "north")
    assert flat_bank.parent_id is None
    flat_conduit = Pathway.objects.get(pk=conduit.pk)
    assert (flat_conduit.parent_id, flat_conduit.position, flat_conduit.material) == (bank.pk, "A1", "pvc")
    flat_duct = Pathway.objects.get(pk=duct.pk)
    assert (flat_duct.parent_id, flat_duct.size, flat_duct.color, flat_duct.position) == (
        conduit.pk,
        "32mm",
        "ff0000",
        "2",
    )
    assert len(str(flat_duct.path).split(".")) == 3
    assert Pathway.objects.get(pk=lateral.pk).start_junction_id == junction.pk
    assert ConduitJunction.objects.get(pk=junction.pk).trunk_conduit_id == conduit.pk
    flat_span = Pathway.objects.get(pk=span.pk)
    assert (flat_span.aerial_type, flat_span.sag) == ("lashed", 1.5)
    flat_buried = Pathway.objects.get(pk=buried.pk)
    assert (flat_buried.burial_depth, flat_buried.warning_tape) == (1.2, True)


@pytest.mark.django_db(transaction=True)
def test_flatten_reverses_into_subtype_rows(migrate_to):
    bank = Pathway.objects.create(pathway_type="conduit_bank", label="UR-B", encasement_type="concrete")
    conduit = Pathway.objects.create(pathway_type="conduit", label="UR-C", parent=bank, position="B2", depth=0.9)
    duct = Pathway.objects.create(pathway_type="innerduct", label="UR-I", parent=conduit, size="25mm")

    old = _legacy_models(migrate_to(BEFORE_FLATTEN))

    assert old["conduitbank"].objects.get(pk=bank.pk).encasement_type == "concrete"
    old_conduit = old["conduit"].objects.get(pk=conduit.pk)
    assert (old_conduit.conduit_bank_id, old_conduit.bank_position, old_conduit.depth) == (bank.pk, "B2", 0.9)
    old_duct = old["innerduct"].objects.get(pk=duct.pk)
    assert (old_duct.parent_conduit_id, old_duct.size) == (conduit.pk, "25mm")


@pytest.mark.django_db
def test_reverse_refuses_a_parent_the_subtype_tables_cannot_hold():
    """Reversing the flatten would drop an innerduct's tray parent; it stops instead."""
    raceway = Pathway.objects.create(pathway_type="raceway", label="UR-RW")
    tray = Pathway.objects.create(pathway_type="tray", label="UR-TR", parent=raceway)
    duct = Pathway.objects.create(pathway_type="innerduct", label="UR-TD", parent=tray)

    with pytest.raises(RuntimeError, match=rf"pathways .*\b{duct.pk}\b"):
        uncopy_subtype_rows(django.apps.apps, None)

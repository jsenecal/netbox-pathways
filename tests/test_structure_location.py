"""Tests for the Structure geometry rename and the new dcim.Location FK (#89).

Three changes are covered here:

- ``Structure.location`` (a GeometryField) is renamed to ``Structure.geometry``.
- ``Structure.location`` becomes a nullable FK to ``dcim.Location``, validated
  in ``clean()`` the way ``Device.clean()`` validates its own site/location pair.
- ``splice_closure`` is dropped from ``StructureTypeChoices``; existing rows are
  blanked by a data migration.
"""

import pytest
from dcim.models import Location, Site
from django.contrib.gis.geos import LineString, Point, Polygon
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from netbox_pathways.choices import StructureTypeChoices
from netbox_pathways.geo import get_srid
from netbox_pathways.models import SiteGeometry, Structure

SRID = get_srid()


@pytest.fixture
def site(db):
    return Site.objects.create(name="Loc-Site", slug="loc-site")


@pytest.fixture
def other_site(db):
    return Site.objects.create(name="Other-Site", slug="other-site")


@pytest.fixture
def dcim_location(site):
    return Location.objects.create(name="Vault Row A", slug="vault-row-a", site=site)


class TestStructureTypeChoices:
    def test_splice_closure_removed(self):
        """A splice closure is Device-shaped (ports, modules) and lives *in* a
        structure, so it must not be selectable as a structure type."""
        assert "splice_closure" not in StructureTypeChoices.values()

    def test_container_types_retained(self):
        values = StructureTypeChoices.values()
        for expected in ("handhole", "pedestal", "cabinet", "manhole", "vault"):
            assert expected in values


@pytest.mark.django_db
class TestStructureGeometryField:
    def test_centroid_reads_geometry(self):
        poly = Polygon(((0, 0), (10, 0), (10, 10), (0, 10), (0, 0)), srid=SRID)
        s = Structure.objects.create(name="GEO-2", geometry=poly)
        assert (s.centroid.x, s.centroid.y) == (5.0, 5.0)


@pytest.mark.django_db
class TestStructureLocationFK:
    def test_location_in_matching_site_is_valid(self, site, dcim_location):
        s = Structure(name="FK-2", geometry=Point(0, 0, srid=SRID), site=site, location=dcim_location)
        s.full_clean()

    def test_location_outside_site_rejected(self, other_site, dcim_location):
        """Mirrors Device.clean(): a location must belong to the assigned site."""
        s = Structure(
            name="FK-3",
            geometry=Point(0, 0, srid=SRID),
            site=other_site,
            location=dcim_location,
        )
        with pytest.raises(ValidationError) as exc:
            s.full_clean()
        assert "location" in exc.value.message_dict

    def test_site_derived_from_location_when_blank(self, site, dcim_location):
        """Structure.site is nullable (unlike Device.site), so a location with
        no site is completed rather than rejected -- this keeps the site-centroid
        map fallback working."""
        s = Structure(name="FK-4", geometry=Point(0, 0, srid=SRID), location=dcim_location)
        s.full_clean()
        assert s.site_id == site.pk


@pytest.mark.django_db
class TestSiteGeometryReadsStructureGeometry:
    def test_save_copies_structure_geometry(self, site):
        """SiteGeometry copies the structure's geometry when blank. After the
        rename, ``structure.location`` is a Location FK -- assigning it to a
        GeometryField would fail at save time, so this pins the right source."""
        structure = Structure.objects.create(name="SG-1", geometry=Point(3, 4, srid=SRID))
        sg = SiteGeometry.objects.create(site=site, structure=structure)
        sg.refresh_from_db()
        assert (sg.geometry.x, sg.geometry.y) == (3.0, 4.0)

    def test_effective_geometry_falls_back_to_structure(self, site):
        structure = Structure.objects.create(name="SG-2", geometry=Point(5, 6, srid=SRID))
        sg = SiteGeometry(site=site, structure=structure)
        assert (sg.effective_geometry.x, sg.effective_geometry.y) == (5.0, 6.0)


@pytest.mark.django_db
class TestStructureFilterSetLocation:
    def test_location_id_filter(self, site, dcim_location):
        from netbox_pathways.filtersets import StructureFilterSet

        inside = Structure.objects.create(
            name="F-IN",
            geometry=Point(0, 0, srid=SRID),
            site=site,
            location=dcim_location,
        )
        Structure.objects.create(name="F-OUT", geometry=Point(1, 1, srid=SRID), site=site)

        fs = StructureFilterSet({"location_id": [dcim_location.pk]}, queryset=Structure.objects.all())
        assert list(fs.qs) == [inside]

    def test_location_slug_filter(self, site, dcim_location):
        from netbox_pathways.filtersets import StructureFilterSet

        inside = Structure.objects.create(
            name="F-SLUG",
            geometry=Point(0, 0, srid=SRID),
            site=site,
            location=dcim_location,
        )
        fs = StructureFilterSet({"location": [dcim_location.slug]}, queryset=Structure.objects.all())
        assert list(fs.qs) == [inside]


@pytest.mark.django_db
class TestStructureImportFormColumns:
    def test_location_column_is_a_location_name_and_geometry_holds_coordinates(self, site, dcim_location):
        """The CSV keeps a `location` column but its meaning flips from
        coordinates to a Location name -- the two must not get re-crossed."""
        from netbox_pathways.forms import StructureImportForm

        form = StructureImportForm(
            data={
                "name": "CSV-1",
                "status": "active",
                "structure_type": "handhole",
                "site": site.name,
                "location": dcim_location.name,
                "geometry": "POINT(-73.5 45.5)",
            }
        )
        assert form.is_valid(), form.errors
        structure = form.save()
        assert structure.location_id == dcim_location.pk
        assert structure.geometry.geom_type == "Point"


class TestGraphQLTypeExposesLocationFK:
    def test_location_is_the_fk_not_the_geometry(self):
        """The strawberry type excludes ``geometry``; leaving the old
        ``exclude=["location"]`` in place would hide the new FK and try to
        expose the GeometryField instead."""
        from netbox_pathways.graphql.types import StructureType

        field_names = {f.name for f in StructureType.__strawberry_definition__.fields}
        assert "geometry" not in field_names
        assert "location" in field_names


@pytest.fixture
def migrate_to():
    """Migrate the netbox_pathways app to a specific migration target."""

    def _do(target_name):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([("netbox_pathways", target_name)])
        return MigrationExecutor(connection)

    return _do


@pytest.fixture(autouse=True)
def _restore_head(request):
    """Re-migrate to the latest migration after any test in this module that
    touched migrations. `--reuse-db` means a stranded schema outlives the run
    and breaks every later test file, so this is not optional."""
    yield
    marker = request.node.get_closest_marker("django_db")
    if marker and marker.kwargs.get("transaction"):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        leaf_nodes = executor.loader.graph.leaf_nodes("netbox_pathways")
        if leaf_nodes:
            executor.migrate([leaf_nodes[0]])


@pytest.mark.django_db(transaction=True)
def test_migration_blanks_splice_closure_structures(migrate_to):
    """Operators reclassify blanked rows to the real container type; asserting
    a replacement type here would put words in their mouth."""
    pre = "0020_pathway_status"
    post = "0021_structure_geometry_and_location"

    executor = migrate_to(pre)
    OldStructure = executor.loader.project_state([("netbox_pathways", pre)]).apps.get_model(
        "netbox_pathways", "Structure"
    )
    OldStructure.objects.create(
        name="closure-row",
        location=Point(0, 0, srid=SRID),
        structure_type="splice_closure",
    )
    OldStructure.objects.create(
        name="handhole-row",
        location=Point(1, 1, srid=SRID),
        structure_type="handhole",
    )

    executor = migrate_to(post)
    NewStructure = executor.loader.project_state([("netbox_pathways", post)]).apps.get_model(
        "netbox_pathways", "Structure"
    )

    assert NewStructure.objects.get(name="closure-row").structure_type == ""
    assert NewStructure.objects.get(name="handhole-row").structure_type == "handhole"
    # The rename must carry the geometry across, not drop it.
    assert NewStructure.objects.get(name="handhole-row").geometry is not None


@pytest.mark.django_db(transaction=True)
def test_migration_reverse_restores_location_column(migrate_to):
    pre = "0020_pathway_status"
    post = "0021_structure_geometry_and_location"

    migrate_to(post)
    executor = MigrationExecutor(connection)
    PostStructure = executor.loader.project_state([("netbox_pathways", post)]).apps.get_model(
        "netbox_pathways", "Structure"
    )
    PostStructure.objects.create(name="rev-row", geometry=Point(7, 8, srid=SRID))

    executor = migrate_to(pre)
    PreStructure = executor.loader.project_state([("netbox_pathways", pre)]).apps.get_model(
        "netbox_pathways", "Structure"
    )
    reverted = PreStructure.objects.get(name="rev-row")
    assert (reverted.location.x, reverted.location.y) == (7.0, 8.0)


@pytest.mark.django_db(transaction=True)
def test_identity_migration_fails_loudly_on_shared_locations(migrate_to):
    """Converting Structure.location to a one-to-one must abort with a message
    naming the shared location, not die on the unique constraint (#90)."""
    pre = "0022_innerduct_color_hex"
    post = "0023_structure_location_identity"

    executor = migrate_to(pre)
    state = executor.loader.project_state([("netbox_pathways", pre)]).apps
    OldStructure = state.get_model("netbox_pathways", "Structure")
    OldSite = state.get_model("dcim", "Site")
    OldLocation = state.get_model("dcim", "Location")

    site = OldSite.objects.create(name="Dup-Site", slug="dup-site")
    # Historical models bypass the MPTT manager, so tree columns are set by hand.
    loc = OldLocation.objects.create(name="Dup-Loc", slug="dup-loc", site=site, lft=1, rght=2, tree_id=1, level=0)
    OldStructure.objects.create(name="dup-1", geometry=Point(0, 0, srid=SRID), location_id=loc.pk)
    OldStructure.objects.create(name="dup-2", geometry=Point(1, 1, srid=SRID), location_id=loc.pk)

    with pytest.raises(RuntimeError, match="shared"):
        migrate_to(post)

    # Unshare so the autouse _restore_head fixture can migrate back to the leaf.
    OldStructure.objects.filter(name="dup-2").update(location_id=None)


@pytest.mark.django_db
def test_pathway_snapping_reads_structure_geometry():
    """Pathway._validate_and_snap_endpoint reads the structure geometry; after
    the rename it must not read the Location FK."""
    from netbox_pathways.models import Conduit

    s1 = Structure.objects.create(name="SNAP-1", geometry=Point(0, 0, srid=SRID))
    s2 = Structure.objects.create(name="SNAP-2", geometry=Point(100, 100, srid=SRID))
    conduit = Conduit(
        label="SNAP-C",
        path=LineString((0.2, 0.2), (99.8, 99.8), srid=SRID),
        start_structure=s1,
        end_structure=s2,
    )
    conduit.pathway_type = "conduit"
    conduit.clean()
    assert conduit.path.coords[0] == (0.0, 0.0)
    assert conduit.path.coords[-1] == (100.0, 100.0)

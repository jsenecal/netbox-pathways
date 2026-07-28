"""Tests for CoreModelMapExtension._get_geo_data -- the map panel injected into
core Site and Location detail pages.

The Location branch could not show the structures inside a location until
`Structure.location` existed (#89): it only showed pathways whose start/end was
the location, plus those pathways' endpoint structures. A location holding
structures but touched by no pathway rendered nothing at all.
"""

import pytest
from dcim.models import Location, Site
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.geo import get_srid
from netbox_pathways.models import Conduit, Structure
from netbox_pathways.template_content import CoreModelMapExtension

SRID = get_srid()


@pytest.fixture
def site(db):
    return Site.objects.create(name="Map Site", slug="map-site")


@pytest.fixture
def room(site):
    return Location.objects.create(site=site, name="Room A", slug="room-a")


def _extension():
    """CoreModelMapExtension only needs a context for render(); _get_geo_data does not."""
    return CoreModelMapExtension(context={})


def _structure(name, x, y, **kwargs):
    return Structure.objects.create(name=name, geometry=Point(x, y, srid=SRID), **kwargs)


def _conduit(**kwargs):
    c = Conduit(**kwargs)
    c.pathway_type = "conduit"
    c.save()
    return c


def _names(data):
    return sorted(p["name"] for p in data["points"])


def _by_name(data):
    return {p["name"]: p for p in data["points"]}


@pytest.mark.django_db
class TestLocationGeoData:
    def test_structures_in_location_are_shown_without_any_pathway(self, site, room):
        """The gap this fixes: a location with structures but no pathways."""
        _structure("MH-1", 0, 0, site=site, location=room)
        _structure("MH-2", 10, 10, site=site, location=room)

        data = _extension()._get_geo_data(room)

        assert data is not None
        assert _names(data) == ["MH-1", "MH-2"]

    def test_structures_elsewhere_are_excluded(self, site, room):
        other = Location.objects.create(site=site, name="Room B", slug="room-b")
        _structure("IN", 0, 0, site=site, location=room)
        _structure("OUT", 10, 10, site=site, location=other)

        data = _extension()._get_geo_data(room)

        assert _names(data) == ["IN"]

    def test_pathway_endpoint_structure_outside_location_still_shown(self, site, room):
        """Pathways leaving the location keep their far-end structure as context."""
        far = _structure("FAR", 100, 100, site=site)
        _conduit(
            label="C-out",
            path=LineString((0, 0), (100, 100), srid=SRID),
            start_location=room,
            end_structure=far,
        )

        data = _extension()._get_geo_data(room)

        assert _names(data) == ["FAR"]
        assert len(data["lines"]) == 1

    def test_structure_both_inside_and_an_endpoint_appears_once(self, site, room):
        """A structure in the location that also terminates a pathway from that
        location must not get two stacked markers."""
        both = _structure("BOTH", 100, 100, site=site, location=room)
        _conduit(
            label="C-both",
            path=LineString((0, 0), (100, 100), srid=SRID),
            start_location=room,
            end_structure=both,
        )

        data = _extension()._get_geo_data(room)

        assert _names(data) == ["BOTH"]

    def test_structure_shared_by_two_pathways_appears_once(self, site, room):
        """Two conduits from the same room to the same manhole stacked its
        marker twice before the dedup."""
        shared = _structure("SHARED", 100, 100, site=site)
        for label in ("C-1", "C-2"):
            _conduit(
                label=label,
                path=LineString((0, 0), (100, 100), srid=SRID),
                start_location=room,
                end_structure=shared,
            )

        data = _extension()._get_geo_data(room)

        assert _names(data) == ["SHARED"]
        assert len(data["lines"]) == 2

    def test_empty_location_returns_none(self, room):
        """No geometry to show means no panel at all, not an empty card."""
        assert _extension()._get_geo_data(room) is None


@pytest.mark.django_db
class TestMutedContextMarkers:
    """Structures the page is *about* render at full strength; structures shown
    only to give a pathway its far end are muted, so a location's own plant
    reads first. The flag is omitted rather than set False so the common case
    adds nothing to the payload.
    """

    def test_far_end_structure_is_muted(self, site, room):
        far = _structure("FAR", 100, 100, site=site)
        _conduit(
            label="C-out",
            path=LineString((0, 0), (100, 100), srid=SRID),
            start_location=room,
            end_structure=far,
        )

        points = _by_name(_extension()._get_geo_data(room))

        assert points["FAR"]["muted"] is True

    def test_structure_in_location_is_not_muted(self, site, room):
        _structure("MINE", 0, 0, site=site, location=room)

        points = _by_name(_extension()._get_geo_data(room))

        assert "muted" not in points["MINE"]

    def test_structure_both_inside_and_far_end_is_not_muted(self, site, room):
        """Being in the location wins -- it is not merely context here."""
        both = _structure("BOTH", 100, 100, site=site, location=room)
        _conduit(
            label="C-both",
            path=LineString((0, 0), (100, 100), srid=SRID),
            start_location=room,
            end_structure=both,
        )

        points = _by_name(_extension()._get_geo_data(room))

        assert "muted" not in points["BOTH"]

    def test_site_panel_structures_are_never_muted(self, site):
        """On a Site page the structures are the subject, not context."""
        _structure("SITE-MH", 0, 0, site=site)

        points = _by_name(_extension()._get_geo_data(site))

        assert "muted" not in points["SITE-MH"]


@pytest.mark.django_db
class TestLocationGeoDataRollsUpTheTree:
    """Core's LocationView counts related objects across
    `get_descendants(include_self=True)`, so the map on that same page has to
    roll up too -- otherwise the Related Objects card reads "Structures: 1"
    beside a map showing nothing.
    """

    def test_structures_in_child_locations_are_included(self, site):
        parent = Location.objects.create(site=site, name="Building 1", slug="bldg-1")
        child = Location.objects.create(site=site, name="Floor 2", slug="floor-2", parent=parent)
        _structure("CHILD-MH", 0, 0, site=site, location=child)

        data = _extension()._get_geo_data(parent)

        assert data is not None
        assert _names(data) == ["CHILD-MH"]

    def test_pathway_anchored_to_a_child_location_is_included(self, site):
        parent = Location.objects.create(site=site, name="Building 2", slug="bldg-2")
        child = Location.objects.create(site=site, name="Riser", slug="riser", parent=parent)
        far = _structure("FAR-2", 100, 100, site=site)
        _conduit(
            label="C-child",
            path=LineString((0, 0), (100, 100), srid=SRID),
            start_location=child,
            end_structure=far,
        )

        data = _extension()._get_geo_data(parent)

        assert data is not None
        assert len(data["lines"]) == 1
        assert _names(data) == ["FAR-2"]

    def test_parent_structures_not_shown_on_child_page(self, site):
        """Roll-up goes down the tree, not up."""
        parent = Location.objects.create(site=site, name="Building 3", slug="bldg-3")
        child = Location.objects.create(site=site, name="Vault", slug="vault", parent=parent)
        _structure("PARENT-MH", 0, 0, site=site, location=parent)

        assert _extension()._get_geo_data(child) is None

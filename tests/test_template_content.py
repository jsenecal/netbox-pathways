"""Tests for CoreModelMapExtension._get_geo_data -- the map panel injected into
core Site and Location detail pages.

The Location branch could not show the structures inside a location until
`Structure.location` existed (#89): it only showed pathways whose start/end was
the location, plus those pathways' endpoint structures. A location holding
structures but touched by no pathway rendered nothing at all.
"""

import pytest
from dcim.models import Location, Site
from django.contrib.gis.geos import LineString, Point, Polygon

from netbox_pathways.geo import get_srid
from netbox_pathways.models import Conduit, Structure
from netbox_pathways.template_content import CoreModelMapExtension, PluginModelMapExtension

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
        """The gap this fixes: a location with structures but no pathways.

        Structure.location is now a one-to-one identity link (#90), so the
        second structure lives in a child location instead of sharing `room`;
        the rollup to descendants covers this same case.
        """
        child = Location.objects.create(site=site, name="Room A-1", slug="room-a-1", parent=room)
        _structure("MH-1", 0, 0, site=site, location=room)
        _structure("MH-2", 10, 10, site=site, location=child)

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


@pytest.mark.django_db
class TestPolygonStructures:
    """A Structure's geometry may be a footprint polygon (#96). Those render as
    the real outline rather than a marker dropped at the centroid; the centroid
    still rides along so the client can collapse the shape to an icon when
    zoomed out past the footprint zoom.
    """

    def _footprint(self, name, **kwargs):
        ring = ((0, 0), (0, 10), (10, 10), (10, 0), (0, 0))
        return Structure.objects.create(
            name=name,
            geometry=Polygon(ring, srid=SRID),
            structure_type="vault",
            **kwargs,
        )

    def test_structure_page_renders_the_footprint_outline(self):
        vault = self._footprint("V-1")

        data = PluginModelMapExtension(context={})._get_geo_data(vault)

        assert data["points"] == []
        assert len(data["polygons"]) == 1
        poly = data["polygons"][0]
        assert poly["name"] == "V-1"
        assert len(poly["coords"]) == 5
        assert poly["coords"][0] == poly["coords"][-1]

    def test_footprint_carries_its_centroid_for_the_collapsed_marker(self):
        vault = self._footprint("V-2")

        poly = PluginModelMapExtension(context={})._get_geo_data(vault)["polygons"][0]

        lons = [c[0] for c in poly["coords"]]
        lats = [c[1] for c in poly["coords"]]
        assert min(lons) < poly["lon"] < max(lons)
        assert min(lats) < poly["lat"] < max(lats)

    def test_point_structures_still_render_as_points(self, site):
        _structure("MH-P", 0, 0, site=site)

        data = PluginModelMapExtension(context={})._get_geo_data(Structure.objects.get(name="MH-P"))

        assert data["polygons"] == []
        assert _names(data) == ["MH-P"]

    def test_footprint_on_a_location_panel_keeps_the_muted_flag(self, site, room):
        far = self._footprint("V-FAR", site=site)
        _conduit(
            label="C-poly",
            path=LineString((0, 0), (100, 100), srid=SRID),
            start_location=room,
            end_structure=far,
        )

        data = _extension()._get_geo_data(room)

        assert [p["name"] for p in data["polygons"]] == ["V-FAR"]
        assert data["polygons"][0]["muted"] is True


@pytest.mark.django_db
class TestPluginModelDetailMaps:
    """Per-model branches of PluginModelMapExtension._get_geo_data."""

    def _plugin_ext(self):
        return PluginModelMapExtension(context={})

    def test_pathway_page_shows_line_with_colored_endpoints(self, site):
        """Start renders green, end renders red, so direction is readable."""
        s1 = _structure("PW-A", 0, 0, site=site)
        s2 = _structure("PW-B", 100, 100, site=site)
        conduit = _conduit(
            label="C-detail",
            path=LineString((0, 0), (100, 100), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )

        data = self._plugin_ext()._get_geo_data(conduit)

        assert len(data["lines"]) == 1
        colors = {p["name"]: p["color"] for p in data["points"]}
        assert colors == {"PW-A": "green", "PW-B": "red"}

    def test_conduit_bank_page_shows_line_and_orange_endpoints(self, site):
        from netbox_pathways.models import ConduitBank

        s1 = _structure("CB-A", 0, 0, site=site)
        s2 = _structure("CB-B", 100, 100, site=site)
        bank = ConduitBank.objects.create(
            label="CB-detail",
            path=LineString((0, 0), (100, 100), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )

        data = self._plugin_ext()._get_geo_data(bank)

        assert len(data["lines"]) == 1
        colors = {p["name"]: p["color"] for p in data["points"]}
        assert colors == {"CB-A": "orange", "CB-B": "orange"}

    def test_junction_page_shows_trunk_line_and_red_junction_point(self, site):
        from netbox_pathways.models import ConduitJunction

        s1 = _structure("JX-A", 0, 0, site=site)
        s2 = _structure("JX-B", 1000, 0, site=site)
        trunk = _conduit(
            label="JX-trunk",
            path=LineString((0, 0), (1000, 0), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )
        branch = _conduit(
            label="JX-branch",
            path=LineString((500, 100), (500, 500), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )
        junction = ConduitJunction.objects.create(
            trunk_conduit=trunk,
            branch_conduit=branch,
            towards_structure=s1,
            position_on_trunk=0.5,
        )

        data = self._plugin_ext()._get_geo_data(junction)

        assert len(data["lines"]) == 1
        assert len(data["points"]) == 1
        assert data["points"][0]["color"] == "red"


@pytest.mark.django_db
class TestSiteBoundary:
    """A SiteGeometry with a polygon footprint draws the site's outline."""

    def test_site_boundary_polygon_rendered_as_line(self, site):
        from netbox_pathways.models import SiteGeometry

        ring = ((0, 0), (0, 100), (100, 100), (100, 0), (0, 0))
        footprint = Structure.objects.create(
            name="SB-vault",
            geometry=Polygon(ring, srid=SRID),
            structure_type="vault",
            site=site,
        )
        SiteGeometry.objects.create(site=site, structure=footprint)

        data = _extension()._get_geo_data(site)

        boundary = [line for line in data["lines"] if line["name"].startswith("Site boundary")]
        assert len(boundary) == 1
        # Closed ring, in [lon, lat] pairs
        assert boundary[0]["coords"][0] == boundary[0]["coords"][-1]

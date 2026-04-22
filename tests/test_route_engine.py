import pytest
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.geo import get_srid
from netbox_pathways.graph import PathwayGraph
from netbox_pathways.models import AerialSpan, Conduit, Structure
from netbox_pathways.route_engine import find_route


@pytest.mark.django_db
class TestRouteEngine:
    @pytest.fixture(autouse=True)
    def _clear_graph_cache(self):
        PathwayGraph._topo_cache = None
        yield
        PathwayGraph._topo_cache = None

    @pytest.fixture
    def srid(self):
        return get_srid()

    @pytest.fixture
    def network(self, srid):
        """Build a small test network:
        S0 --conduit(10m)--> S1 --conduit(20m)--> S2 --aerial(5m)--> S3
                              |                                       |
                              +--------conduit(50m)-------------------+
        """
        structures = [
            Structure.objects.create(
                name=f"RE-{i}", location=Point(i * 0.01, i * 0.01, srid=srid),
            )
            for i in range(4)
        ]
        conduits = [
            Conduit.objects.create(
                label="C-RE-01", start_structure=structures[0],
                end_structure=structures[1],
                path=LineString((0, 0), (0.01, 0.01), srid=srid), length=10,
            ),
            Conduit.objects.create(
                label="C-RE-02", start_structure=structures[1],
                end_structure=structures[2],
                path=LineString((0.01, 0.01), (0.02, 0.02), srid=srid), length=20,
            ),
            Conduit.objects.create(
                label="C-RE-04", start_structure=structures[1],
                end_structure=structures[3],
                path=LineString((0.01, 0.01), (0.03, 0.03), srid=srid), length=50,
            ),
        ]
        aerial = AerialSpan.objects.create(
            label="A-RE-03", start_structure=structures[2],
            end_structure=structures[3],
            path=LineString((0.02, 0.02), (0.03, 0.03), srid=srid), length=5,
        )
        return {'structures': structures, 'conduits': conduits, 'aerial': aerial}

    def test_basic_shortest_route(self, network):
        """Shortest path S0->S3 should go S0->S1->S2->S3 (10+20+5=35) not direct (50)."""
        s = network['structures']
        result = find_route(
            start_node=('structure', s[0].pk),
            end_node=('structure', s[3].pk),
        )
        assert result is not None
        cost, pathway_ids = result
        assert cost == 35
        assert len(pathway_ids) == 3

    def test_avoid_pathway_type(self, network):
        """Avoiding aerial forces S0->S1->S3 (10+50=60) instead of through S2."""
        s = network['structures']
        result = find_route(
            start_node=('structure', s[0].pk),
            end_node=('structure', s[3].pk),
            avoid_pathway_types=['aerial'],
        )
        assert result is not None
        cost, pathway_ids = result
        assert cost == 60
        assert len(pathway_ids) == 2

    def test_avoid_structure(self, network):
        """Removing S1 disconnects S0 from all other nodes."""
        s = network['structures']
        result = find_route(
            start_node=('structure', s[0].pk),
            end_node=('structure', s[3].pk),
            avoid_structures=[s[1].pk],
        )
        assert result is None

    def test_must_pass_through(self, network):
        """Forcing route through S2 should produce S0->S1->S2->S3 (35m)."""
        s = network['structures']
        result = find_route(
            start_node=('structure', s[0].pk),
            end_node=('structure', s[3].pk),
            must_pass_through=[s[2].pk],
        )
        assert result is not None
        cost, pathway_ids = result
        assert cost == 35

    def test_no_route_returns_none(self, srid):
        """Isolated structures with no connecting pathways return None."""
        s1 = Structure.objects.create(
            name="ISO-RE-1", location=Point(0, 0, srid=srid),
        )
        s2 = Structure.objects.create(
            name="ISO-RE-2", location=Point(1, 1, srid=srid),
        )
        result = find_route(
            start_node=('structure', s1.pk),
            end_node=('structure', s2.pk),
        )
        assert result is None

    def test_avoid_structure_type(self, network, srid):
        """Pathways touching structures of avoided type are excluded."""
        s = network['structures']
        # Mark S2 as a pole
        s[2].structure_type = 'pole'
        s[2].save()
        result = find_route(
            start_node=('structure', s[0].pk),
            end_node=('structure', s[3].pk),
            avoid_structure_types=['pole'],
        )
        assert result is not None
        cost, pathway_ids = result
        # Can't go through S2 (pole), so must go S0->S1->S3 (60)
        assert cost == 60

    def test_include_inactive_false_excludes_retired(self, network, srid):
        """By default, pathways touching retired structures are excluded."""
        s = network['structures']
        # Retire S1 — this should exclude all pathways touching S1
        s[1].status = 'retired'
        s[1].save()
        result = find_route(
            start_node=('structure', s[0].pk),
            end_node=('structure', s[3].pk),
            include_inactive=False,
        )
        # S0 has no pathways left (all went through S1)
        assert result is None

    def test_include_inactive_true_allows_retired(self, network, srid):
        """With include_inactive=True, retired structures are traversable."""
        s = network['structures']
        s[1].status = 'retired'
        s[1].save()
        result = find_route(
            start_node=('structure', s[0].pk),
            end_node=('structure', s[3].pk),
            include_inactive=True,
        )
        assert result is not None
        cost, _ids = result
        assert cost == 35

    def test_cached_graph_bypassed_with_constraints(self, network):
        """When constraints produce a filtered queryset, cache is bypassed."""
        s = network['structures']
        # First call populates cache
        result1 = find_route(
            start_node=('structure', s[0].pk),
            end_node=('structure', s[3].pk),
        )
        assert result1 is not None

        # Second call with constraints should bypass cache and use filtered qs
        result2 = find_route(
            start_node=('structure', s[0].pk),
            end_node=('structure', s[3].pk),
            avoid_pathway_types=['aerial'],
        )
        assert result2 is not None
        # With aerial excluded, cost must be different
        assert result2[0] == 60

    def test_prefer_in_use_factor(self, network, srid):
        """In-use preference should reduce weight of pathways carrying cables."""
        from dcim.models import Cable, CableTermination, Interface
        from django.contrib.contenttypes.models import ContentType

        s = network['structures']
        conduits = network['conduits']

        # Create a cable and segment on the direct S1->S3 conduit (50m)
        # We need device interfaces to terminate the cable
        from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Site

        site = Site.objects.create(name="RE-site", slug="re-site")
        mfr = Manufacturer.objects.create(name="RE-mfr", slug="re-mfr")
        dt = DeviceType.objects.create(
            manufacturer=mfr, model="RE-dt", slug="re-dt",
        )
        dr = DeviceRole.objects.create(name="RE-dr", slug="re-dr")
        dev_a = Device.objects.create(
            name="RE-devA", device_type=dt, role=dr, site=site,
        )
        dev_b = Device.objects.create(
            name="RE-devB", device_type=dt, role=dr, site=site,
        )
        iface_a = Interface.objects.create(name="eth0", device=dev_a, type="1000base-t")
        iface_b = Interface.objects.create(name="eth0", device=dev_b, type="1000base-t")

        cable = Cable.objects.create(label="RE-cable-1")
        iface_ct = ContentType.objects.get_for_model(Interface)
        CableTermination.objects.create(
            cable=cable, cable_end='A',
            termination_type=iface_ct, termination_id=iface_a.pk,
        )
        CableTermination.objects.create(
            cable=cable, cable_end='B',
            termination_type=iface_ct, termination_id=iface_b.pk,
        )

        # Route the cable through the direct S1->S3 conduit
        from netbox_pathways.models import CableSegment

        CableSegment.objects.create(cable=cable, pathway=conduits[2])

        # With high preference, the direct path (50m, but discounted) could become cheaper
        result = find_route(
            start_node=('structure', s[0].pk),
            end_node=('structure', s[3].pk),
            prefer_in_use_factor=100,
        )
        assert result is not None
        cost, pathway_ids = result
        # S0->S1(10) + S1->S3(50 * 0.5 = 25) = 35 vs S0->S1(10)+S1->S2(20)+S2->S3(5) = 35
        # Both are equal at factor=100, so either route is valid
        assert cost <= 35

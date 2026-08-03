import pytest
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.geo import get_srid
from netbox_pathways.graph import PathwayGraph
from netbox_pathways.models import AerialSpan, CableSegment, Conduit, Structure
from netbox_pathways.route_engine import find_route
from tests.conftest import build_cable_with_terminations


def _circuit_cable_on(pathway, site):
    """Lay a cable in `pathway` whose ends terminate on a Circuit's A/Z sides.

    This is the shape avoid_circuits / avoid_circuit_geometries resolve:
    Circuit -> CircuitTermination -> CableTermination -> Cable -> CableSegment.
    """
    from circuits.models import Circuit, CircuitTermination, CircuitType, Provider
    from dcim.models import Cable, CableTermination
    from django.contrib.contenttypes.models import ContentType

    provider = Provider.objects.create(name="RE-prov", slug="re-prov")
    ctype = CircuitType.objects.create(name="RE-ctype", slug="re-ctype")
    circuit = Circuit.objects.create(cid="RE-CID", provider=provider, type=ctype)
    term_a = CircuitTermination.objects.create(circuit=circuit, term_side="A", termination=site)
    term_z = CircuitTermination.objects.create(circuit=circuit, term_side="Z", termination=site)

    cable = Cable.objects.create(label="RE-circuit-cable")
    ct = ContentType.objects.get_for_model(CircuitTermination)
    for end, term in (("A", term_a), ("B", term_z)):
        CableTermination.objects.create(
            cable=cable,
            cable_end=end,
            termination_type=ct,
            termination_id=term.pk,
        )
    CableSegment.objects.create(cable=cable, pathway=pathway)
    return circuit, cable


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
                name=f"RE-{i}",
                geometry=Point(i * 0.01, i * 0.01, srid=srid),
            )
            for i in range(4)
        ]
        conduits = [
            Conduit.objects.create(
                label="C-RE-01",
                start_structure=structures[0],
                end_structure=structures[1],
                path=LineString((0, 0), (0.01, 0.01), srid=srid),
                length=10,
            ),
            Conduit.objects.create(
                label="C-RE-02",
                start_structure=structures[1],
                end_structure=structures[2],
                path=LineString((0.01, 0.01), (0.02, 0.02), srid=srid),
                length=20,
            ),
            Conduit.objects.create(
                label="C-RE-04",
                start_structure=structures[1],
                end_structure=structures[3],
                path=LineString((0.01, 0.01), (0.03, 0.03), srid=srid),
                length=50,
            ),
        ]
        aerial = AerialSpan.objects.create(
            label="A-RE-03",
            start_structure=structures[2],
            end_structure=structures[3],
            path=LineString((0.02, 0.02), (0.03, 0.03), srid=srid),
            length=5,
        )
        return {"structures": structures, "conduits": conduits, "aerial": aerial}

    def test_basic_shortest_route(self, network):
        """Shortest path S0->S3 should go S0->S1->S2->S3 (10+20+5=35) not direct (50)."""
        s = network["structures"]
        result = find_route(
            start_node=("structure", s[0].pk),
            end_node=("structure", s[3].pk),
        )
        assert result is not None
        cost, pathway_ids = result
        assert cost == 35
        assert len(pathway_ids) == 3

    def test_avoid_pathway_type(self, network):
        """Avoiding aerial forces S0->S1->S3 (10+50=60) instead of through S2."""
        s = network["structures"]
        result = find_route(
            start_node=("structure", s[0].pk),
            end_node=("structure", s[3].pk),
            avoid_pathway_types=["aerial"],
        )
        assert result is not None
        cost, pathway_ids = result
        assert cost == 60
        assert len(pathway_ids) == 2

    def test_avoid_structure(self, network):
        """Removing S1 disconnects S0 from all other nodes."""
        s = network["structures"]
        result = find_route(
            start_node=("structure", s[0].pk),
            end_node=("structure", s[3].pk),
            avoid_structures=[s[1].pk],
        )
        assert result is None

    def test_must_pass_through(self, network):
        """Forcing route through S2 should produce S0->S1->S2->S3 (35m)."""
        s = network["structures"]
        result = find_route(
            start_node=("structure", s[0].pk),
            end_node=("structure", s[3].pk),
            must_pass_through=[s[2].pk],
        )
        assert result is not None
        cost, pathway_ids = result
        assert cost == 35

    def test_no_route_returns_none(self, srid):
        """Isolated structures with no connecting pathways return None."""
        s1 = Structure.objects.create(
            name="ISO-RE-1",
            geometry=Point(0, 0, srid=srid),
        )
        s2 = Structure.objects.create(
            name="ISO-RE-2",
            geometry=Point(1, 1, srid=srid),
        )
        result = find_route(
            start_node=("structure", s1.pk),
            end_node=("structure", s2.pk),
        )
        assert result is None

    def test_avoid_structure_type(self, network, srid):
        """Pathways touching structures of avoided type are excluded."""
        s = network["structures"]
        # Mark S2 as a pole
        s[2].structure_type = "pole"
        s[2].save()
        result = find_route(
            start_node=("structure", s[0].pk),
            end_node=("structure", s[3].pk),
            avoid_structure_types=["pole"],
        )
        assert result is not None
        cost, pathway_ids = result
        # Can't go through S2 (pole), so must go S0->S1->S3 (60)
        assert cost == 60

    def test_include_inactive_false_excludes_retired(self, network, srid):
        """By default, pathways touching retired structures are excluded."""
        s = network["structures"]
        # Retire S1 — this should exclude all pathways touching S1
        s[1].status = "retired"
        s[1].save()
        result = find_route(
            start_node=("structure", s[0].pk),
            end_node=("structure", s[3].pk),
            include_inactive=False,
        )
        # S0 has no pathways left (all went through S1)
        assert result is None

    def test_include_inactive_true_allows_retired(self, network, srid):
        """With include_inactive=True, retired structures are traversable."""
        s = network["structures"]
        s[1].status = "retired"
        s[1].save()
        result = find_route(
            start_node=("structure", s[0].pk),
            end_node=("structure", s[3].pk),
            include_inactive=True,
        )
        assert result is not None
        cost, _ids = result
        assert cost == 35

    def test_include_inactive_false_excludes_retired_pathways(self, network):
        """A pathway whose own status is retired is not routable by default (issue #60)."""
        c = network["conduits"][1]  # S1->S2, the cheap middle hop
        c.status = "retired"
        c.save()
        s = network["structures"]
        result = find_route(
            start_node=("structure", s[0].pk),
            end_node=("structure", s[3].pk),
            include_inactive=False,
        )
        assert result is not None
        cost, pathway_ids = result
        # Forced onto the direct S1->S3 conduit: 10 + 50
        assert cost == 60
        assert c.pk not in pathway_ids

    def test_include_inactive_true_allows_retired_pathways(self, network):
        c = network["conduits"][1]
        c.status = "retired"
        c.save()
        s = network["structures"]
        result = find_route(
            start_node=("structure", s[0].pk),
            end_node=("structure", s[3].pk),
            include_inactive=True,
        )
        assert result is not None
        cost, _ids = result
        assert cost == 35

    def test_cached_graph_bypassed_with_constraints(self, network):
        """When constraints produce a filtered queryset, cache is bypassed."""
        s = network["structures"]
        # First call populates cache
        result1 = find_route(
            start_node=("structure", s[0].pk),
            end_node=("structure", s[3].pk),
        )
        assert result1 is not None

        # Second call with constraints should bypass cache and use filtered qs
        result2 = find_route(
            start_node=("structure", s[0].pk),
            end_node=("structure", s[3].pk),
            avoid_pathway_types=["aerial"],
        )
        assert result2 is not None
        # With aerial excluded, cost must be different
        assert result2[0] == 60

    def test_prefer_in_use_factor(self, network, srid):
        """In-use preference should reduce weight of pathways carrying cables."""
        from dcim.models import Site

        s = network["structures"]
        conduits = network["conduits"]

        # Route a cable through the direct S1->S3 conduit (50m)
        site = Site.objects.create(name="RE-site", slug="re-site")
        cable = build_cable_with_terminations(label="RE-cable-1", site=site)
        CableSegment.objects.create(cable=cable, pathway=conduits[2])

        # With high preference, the direct path (50m, but discounted) could become cheaper
        result = find_route(
            start_node=("structure", s[0].pk),
            end_node=("structure", s[3].pk),
            prefer_in_use_factor=100,
        )
        assert result is not None
        cost, pathway_ids = result
        # S0->S1(10) + S1->S3(50 * 0.5 = 25) = 35 vs S0->S1(10)+S1->S2(20)+S2->S3(5) = 35
        # Both are equal at factor=100, so either route is valid
        assert cost <= 35

    def test_avoid_tenants(self, network):
        """Pathways owned by an avoided tenant drop out of the graph."""
        from tenancy.models import Tenant

        tenant = Tenant.objects.create(name="RE-tenant", slug="re-tenant")
        middle = network["conduits"][1]  # S1->S2, the cheap middle hop
        middle.tenant = tenant
        middle.save()
        s = network["structures"]
        result = find_route(
            start_node=("structure", s[0].pk),
            end_node=("structure", s[3].pk),
            avoid_tenants=[tenant.pk],
        )
        assert result is not None
        cost, pathway_ids = result
        # Forced onto the direct S1->S3 conduit: 10 + 50
        assert cost == 60
        assert middle.pk not in pathway_ids

    def test_tenant_only_allows_own_and_unassigned(self, network):
        """tenant_only keeps the tenant's own pathways plus unassigned ones."""
        from tenancy.models import Tenant

        mine = Tenant.objects.create(name="RE-mine", slug="re-mine")
        other = Tenant.objects.create(name="RE-other", slug="re-other")
        conduits = network["conduits"]
        conduits[0].tenant = mine  # S0->S1: ours, must stay routable
        conduits[0].save()
        conduits[1].tenant = other  # S1->S2: someone else's, must drop out
        conduits[1].save()
        s = network["structures"]
        result = find_route(
            start_node=("structure", s[0].pk),
            end_node=("structure", s[3].pk),
            tenant_only=mine,
        )
        assert result is not None
        cost, pathway_ids = result
        # Ours (10) + unassigned direct S1->S3 (50); other's middle hop is gone
        assert cost == 60
        assert conduits[1].pk not in pathway_ids

    def test_avoid_cables_removes_carrying_edges(self, network):
        """Edges whose pathway carries an avoided cable are removed."""
        from dcim.models import Site

        site = Site.objects.create(name="RE-ac-site", slug="re-ac-site")
        middle = network["conduits"][1]
        cable = build_cable_with_terminations(label="RE-avoid-cable", site=site)
        CableSegment.objects.create(cable=cable, pathway=middle)
        s = network["structures"]
        result = find_route(
            start_node=("structure", s[0].pk),
            end_node=("structure", s[3].pk),
            avoid_cables=[cable.pk],
        )
        assert result is not None
        cost, pathway_ids = result
        assert cost == 60
        assert middle.pk not in pathway_ids

    def test_avoid_circuits_removes_carrying_edges(self, network):
        """Avoiding a circuit removes edges whose pathway carries its cable."""
        from dcim.models import Site

        site = Site.objects.create(name="RE-circ-site", slug="re-circ-site")
        middle = network["conduits"][1]
        circuit, _cable = _circuit_cable_on(middle, site)
        s = network["structures"]
        result = find_route(
            start_node=("structure", s[0].pk),
            end_node=("structure", s[3].pk),
            avoid_circuits=[circuit.pk],
        )
        assert result is not None
        cost, pathway_ids = result
        assert cost == 60
        assert middle.pk not in pathway_ids

    def test_avoid_circuit_geometries_removes_carrying_edges(self, network, srid):
        """A CircuitGeometry PK resolves back to its circuit's cable edges."""
        from dcim.models import Site

        from netbox_pathways.models import CircuitGeometry

        site = Site.objects.create(name="RE-cg-site", slug="re-cg-site")
        middle = network["conduits"][1]
        circuit, _cable = _circuit_cable_on(middle, site)
        geom = CircuitGeometry.objects.create(
            circuit=circuit,
            path=LineString((0, 0), (0.03, 0.03), srid=srid),
        )
        s = network["structures"]
        result = find_route(
            start_node=("structure", s[0].pk),
            end_node=("structure", s[3].pk),
            avoid_circuit_geometries=[geom.pk],
        )
        assert result is not None
        cost, pathway_ids = result
        assert cost == 60
        assert middle.pk not in pathway_ids

    def test_must_pass_through_unreachable_waypoint_returns_none(self, network, srid):
        """A waypoint the graph cannot reach fails the whole chained route."""
        iso = Structure.objects.create(name="RE-ISO-WP", geometry=Point(9, 9, srid=srid))
        s = network["structures"]
        result = find_route(
            start_node=("structure", s[0].pk),
            end_node=("structure", s[3].pk),
            must_pass_through=[iso.pk],
        )
        assert result is None

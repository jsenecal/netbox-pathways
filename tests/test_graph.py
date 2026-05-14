import pytest
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.geo import get_srid
from netbox_pathways.graph import (
    PathwayGraph,
    batch_resolve_nodes,
    connected_pathways_db,
    node_to_geo,
    node_to_label,
    trace_cable,
)
from netbox_pathways.models import (
    CableSegment,
    Conduit,
    ConduitJunction,
    Pathway,
    Structure,
)


@pytest.mark.django_db
class TestPathwayGraph:
    @pytest.fixture
    def srid(self):
        return get_srid()

    @pytest.fixture
    def structures(self, srid):
        """Create a chain: S0 -- S1 -- S2 -- S3"""
        return [
            Structure.objects.create(
                name=f"G-{i}",
                location=Point(i * 0.01, i * 0.01, srid=srid),
            )
            for i in range(4)
        ]

    @pytest.fixture
    def pathways(self, structures, srid):
        """Create conduits: S0-S1 (10m), S1-S2 (20m), S2-S3 (5m), S0-S3 shortcut (50m)"""
        pws = []
        pairs = [(0, 1, 10), (1, 2, 20), (2, 3, 5), (0, 3, 50)]
        for a, b, length in pairs:
            pws.append(
                Conduit.objects.create(
                    label=f"C-{a}-{b}",
                    start_structure=structures[a],
                    end_structure=structures[b],
                    path=LineString(
                        (a * 0.01, a * 0.01),
                        (b * 0.01, b * 0.01),
                        srid=srid,
                    ),
                    length=length,
                )
            )
        return pws

    def test_build_creates_graph(self, pathways):
        graph = PathwayGraph.build()
        assert graph.node_count >= 4
        assert graph.edge_count >= 4

    def test_shortest_path_by_length(self, structures, pathways):
        graph = PathwayGraph.build()
        start = ("structure", structures[0].pk)
        end = ("structure", structures[3].pk)
        result = graph.shortest_path(start, end)
        assert result is not None
        cost, path_ids = result
        # Shortest by length: S0->S1(10) + S1->S2(20) + S2->S3(5) = 35 < direct 50
        assert cost == 35
        assert len(path_ids) == 3

    def test_shortest_path_no_route(self, srid):
        """Disconnected nodes return None."""
        s1 = Structure.objects.create(name="ISO-1", location=Point(0, 0, srid=srid))
        s2 = Structure.objects.create(name="ISO-2", location=Point(1, 1, srid=srid))
        graph = PathwayGraph.build()
        result = graph.shortest_path(("structure", s1.pk), ("structure", s2.pk))
        assert result is None

    def test_all_routes(self, structures, pathways):
        graph = PathwayGraph.build()
        start = ("structure", structures[0].pk)
        end = ("structure", structures[3].pk)
        routes = graph.all_routes(start, end)
        # Two routes: S0->S1->S2->S3 (35m) and S0->S3 (50m)
        assert len(routes) == 2
        # Sorted by cost
        assert routes[0][0] <= routes[1][0]

    def test_astar_path(self, structures, pathways):
        graph = PathwayGraph.build()
        start = ("structure", structures[0].pk)
        end = ("structure", structures[3].pk)
        result = graph.astar_path(start, end)
        assert result is not None
        cost, path_ids = result
        assert cost == 35

    def test_connected_pathways(self, structures, pathways):
        graph = PathwayGraph.build()
        node = ("structure", structures[0].pk)
        connected = graph.connected_pathways(node)
        # S0 connects to S1 and S3
        assert len(connected) == 2
        dest_nodes = {c["destination"] for c in connected}
        assert ("structure", structures[1].pk) in dest_nodes
        assert ("structure", structures[3].pk) in dest_nodes

    def test_connected_pathways_unknown_node(self, pathways):
        """Unknown nodes return an empty list, not an error (line 307)."""
        graph = PathwayGraph.build()
        assert graph.connected_pathways(("structure", 99999999)) == []

    def test_neighbors_bfs_expands_within_max_hops(self, structures, pathways):
        """BFS returns reachable nodes with hops and accumulated cost (lines 327-357)."""
        graph = PathwayGraph.build()
        start = ("structure", structures[0].pk)
        # max_hops=1 -> only direct neighbors
        one_hop = graph.neighbors(start, max_hops=1)
        # S0 connects directly to S1 and S3
        assert ("structure", structures[1].pk) in one_hop
        assert ("structure", structures[3].pk) in one_hop
        # S2 is two hops away, must not appear at max_hops=1
        assert ("structure", structures[2].pk) not in one_hop
        # Each result is (dist, hops, [pathway_ids])
        dist, hops, ids = one_hop[("structure", structures[1].pk)]
        assert hops == 1
        assert dist == 10
        assert len(ids) == 1

    def test_neighbors_bfs_two_hops(self, structures, pathways):
        """BFS at max_hops=2 reaches S2 via S1."""
        graph = PathwayGraph.build()
        start = ("structure", structures[0].pk)
        two_hop = graph.neighbors(start, max_hops=2)
        # S2 reached via S0->S1->S2 (10 + 20 = 30) at 2 hops
        assert ("structure", structures[2].pk) in two_hop
        dist, hops, ids = two_hop[("structure", structures[2].pk)]
        assert hops == 2
        assert dist == 30
        assert len(ids) == 2

    def test_neighbors_unknown_node(self, pathways):
        """neighbors() returns empty dict when start_node not in graph."""
        graph = PathwayGraph.build()
        assert graph.neighbors(("structure", 99999999)) == {}

    def test_all_routes_unknown_node(self, structures, pathways):
        """all_routes returns [] when either endpoint not in graph (line 286)."""
        graph = PathwayGraph.build()
        start = ("structure", structures[0].pk)
        assert graph.all_routes(start, ("structure", 99999999)) == []
        assert graph.all_routes(("structure", 99999999), start) == []

    def test_all_routes_respects_max_routes(self, structures, pathways):
        """max_routes caps the number of routes returned (line 299)."""
        graph = PathwayGraph.build()
        start = ("structure", structures[0].pk)
        end = ("structure", structures[3].pk)
        # Two simple paths exist; cap at 1
        routes = graph.all_routes(start, end, max_routes=1)
        assert len(routes) == 1

    def test_astar_no_path_returns_none(self, srid):
        """A* returns None when no path exists between nodes (lines 279-280)."""
        s1 = Structure.objects.create(name="AS-1", location=Point(0, 0, srid=srid))
        s2 = Structure.objects.create(name="AS-2", location=Point(1, 1, srid=srid))
        # Pathways exist for s1 only so both nodes are in the graph but disconnected.
        Conduit.objects.create(
            label="AS-self-loop",
            start_structure=s1,
            end_structure=s1,
            path=LineString((0, 0), (0, 0), srid=srid),
            length=1,
        )
        graph = PathwayGraph.build()
        # s2 not in graph -> astar handles NodeNotFound branch
        assert graph.astar_path(("structure", s1.pk), ("structure", s2.pk)) is None

    def test_shortest_path_returns_none_on_unknown_node(self, structures, pathways):
        """shortest_path returns None when an endpoint is not in the graph (NodeNotFound)."""
        graph = PathwayGraph.build()
        start = ("structure", structures[0].pk)
        assert graph.shortest_path(start, ("structure", 99999999)) is None

    def test_haversine_returns_zero_when_geo_missing(self, structures, pathways):
        """A* heuristic returns 0 when either node lacks geo metadata (line 374).

        build_topology() (vs build()) skips geo annotations entirely, so every
        node has geo=None -- triggering the heuristic's no-geo short-circuit.
        """
        topo = PathwayGraph.build_topology()
        start = ("structure", structures[0].pk)
        end = ("structure", structures[3].pk)
        assert topo._haversine_heuristic(start, end) == 0

    def test_shortest_path_nodes_returns_node_list(self, structures, pathways):
        """shortest_path_nodes returns (cost, pathway_ids, nodes) tuple."""
        graph = PathwayGraph.build()
        start = ("structure", structures[0].pk)
        end = ("structure", structures[3].pk)
        result = graph.shortest_path_nodes(start, end)
        assert result is not None
        cost, pathway_ids, nodes = result
        assert cost == 35
        # The node list starts and ends at the requested endpoints
        assert nodes[0] == start
        assert nodes[-1] == end


# ---------------------------------------------------------------------------
# build_topology branches: location endpoints, junctions, start==end skip, cache
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBuildTopology:
    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        PathwayGraph._topo_cache = None
        yield
        PathwayGraph._topo_cache = None

    @pytest.fixture
    def srid(self):
        return get_srid()

    def test_build_endpoint_nodes_location_and_junction_branches(self, srid):
        """_endpoint_nodes uses location/junction fallbacks (lines 24-30, 36-38).

        Reached through build() (not build_topology), which calls _endpoint_nodes
        on annotated Pathway instances.
        """
        from dcim.models import Location, Site

        site = Site.objects.create(name="ep-site", slug="ep-site")
        loc_a = Location.objects.create(name="ep-loc-a", slug="ep-loc-a", site=site)
        loc_b = Location.objects.create(name="ep-loc-b", slug="ep-loc-b", site=site)
        # Pathway with location-only endpoints exercises start_location_id /
        # end_location_id branches in _endpoint_nodes.
        Pathway.objects.create(
            label="ep-loc-only",
            pathway_type="conduit",
            path=LineString((0, 0), (1, 1), srid=srid),
            start_location=loc_a,
            end_location=loc_b,
        )

        # Conduit with a junction endpoint exercises the _start_junction_id /
        # _end_junction_id annotation branches.
        s0 = Structure.objects.create(name="ep-s0", location=Point(0, 0, srid=srid))
        s1 = Structure.objects.create(name="ep-s1", location=Point(0.02, 0.02, srid=srid))
        s2 = Structure.objects.create(name="ep-s2", location=Point(0.03, 0.01, srid=srid))
        trunk = Conduit.objects.create(
            label="ep-trunk",
            start_structure=s0,
            end_structure=s1,
            path=LineString((0, 0), (0.02, 0.02), srid=srid),
            length=100,
        )
        stub = Conduit.objects.create(
            label="ep-stub",
            start_structure=s2,
            end_structure=s2,
            path=LineString((0.03, 0.01), (0.03, 0.01), srid=srid),
            length=1,
        )
        junction = ConduitJunction.objects.create(
            label="ep-J",
            trunk_conduit=trunk,
            branch_conduit=stub,
            towards_structure=s1,
            position_on_trunk=0.5,
        )
        Conduit.objects.create(
            label="ep-branch",
            start_junction=junction,
            end_structure=s2,
            path=LineString((0.01, 0.01), (0.03, 0.01), srid=srid),
            length=20,
        )
        # Second branch with junction as the END endpoint exercises the
        # `end_junc` branch in _endpoint_nodes (line 38).
        Conduit.objects.create(
            label="ep-branch-end",
            start_structure=s2,
            end_junction=junction,
            path=LineString((0.03, 0.01), (0.01, 0.01), srid=srid),
            length=21,
        )

        graph = PathwayGraph.build()
        # Location nodes wired in via _endpoint_nodes location branches
        assert ("location", loc_a.pk) in graph.graph
        assert ("location", loc_b.pk) in graph.graph
        # Junction node wired in via _endpoint_nodes junction branches
        assert ("junction", junction.pk) in graph.graph

    def test_build_filters_by_site_id(self, srid):
        """_build_base applies a Q(start_structure__site_id|end_structure__site_id) filter (line 194)."""
        from dcim.models import Site

        site_a = Site.objects.create(name="bf-site-a", slug="bf-site-a")
        site_b = Site.objects.create(name="bf-site-b", slug="bf-site-b")
        a1 = Structure.objects.create(name="bf-a1", location=Point(0, 0, srid=srid), site=site_a)
        a2 = Structure.objects.create(name="bf-a2", location=Point(0.01, 0.01, srid=srid), site=site_a)
        b1 = Structure.objects.create(name="bf-b1", location=Point(1, 1, srid=srid), site=site_b)
        b2 = Structure.objects.create(name="bf-b2", location=Point(1.01, 1.01, srid=srid), site=site_b)
        Pathway.objects.create(
            label="bf-a-pw",
            pathway_type="conduit",
            path=LineString((0, 0), (0.01, 0.01), srid=srid),
            start_structure=a1,
            end_structure=a2,
        )
        Pathway.objects.create(
            label="bf-b-pw",
            pathway_type="conduit",
            path=LineString((1, 1), (1.01, 1.01), srid=srid),
            start_structure=b1,
            end_structure=b2,
        )
        graph = PathwayGraph.build(site_id=site_a.pk)
        # Only site_a's pathway nodes should appear
        assert ("structure", a1.pk) in graph.graph
        assert ("structure", a2.pk) in graph.graph
        assert ("structure", b1.pk) not in graph.graph
        assert ("structure", b2.pk) not in graph.graph

    def test_build_topology_location_endpoints(self, srid):
        """Pathways with start_location / end_location create location nodes (lines 113-118)."""
        from dcim.models import Location, Site

        site = Site.objects.create(name="topo-site", slug="topo-site")
        loc_a = Location.objects.create(name="topo-loc-a", slug="topo-loc-a", site=site)
        loc_b = Location.objects.create(name="topo-loc-b", slug="topo-loc-b", site=site)
        # Pathway with location-only endpoints (no structures)
        Pathway.objects.create(
            label="loc-only",
            pathway_type="conduit",
            path=LineString((0, 0), (1, 1), srid=srid),
            start_location=loc_a,
            end_location=loc_b,
        )
        topo = PathwayGraph.build_topology()
        assert ("location", loc_a.pk) in topo.graph
        assert ("location", loc_b.pk) in topo.graph
        assert topo.graph.has_edge(("location", loc_a.pk), ("location", loc_b.pk))

    def test_build_topology_skips_self_loop(self, srid):
        """A pathway whose start and end resolve to the same node is skipped (line 121)."""
        s = Structure.objects.create(name="self-loop", location=Point(0, 0, srid=srid))
        Pathway.objects.create(
            label="self",
            pathway_type="conduit",
            path=LineString((0, 0), (0, 0), srid=srid),
            start_structure=s,
            end_structure=s,
        )
        topo = PathwayGraph.build_topology()
        # The self-loop pathway must not produce any edge for this node
        if ("structure", s.pk) in topo.graph:
            assert topo.graph.degree(("structure", s.pk)) == 0

    def test_build_topology_cache_returns_same_instance(self, srid):
        """A second call within TTL returns the cached instance (line 87)."""
        Structure.objects.create(name="cache-s", location=Point(0, 0, srid=srid))
        first = PathwayGraph.build_topology()
        second = PathwayGraph.build_topology()
        assert first is second

    def test_build_topology_with_qs_bypasses_cache(self, srid):
        """Passing pathway_qs bypasses the cache entirely (use_cache=False branch)."""
        s1 = Structure.objects.create(name="qs-s1", location=Point(0, 0, srid=srid))
        s2 = Structure.objects.create(name="qs-s2", location=Point(0.01, 0.01, srid=srid))
        pw = Pathway.objects.create(
            label="qs-pw",
            pathway_type="conduit",
            path=LineString((0, 0), (0.01, 0.01), srid=srid),
            start_structure=s1,
            end_structure=s2,
            length=42,
        )
        # Provide a queryset filtered to only this pathway
        qs = Pathway.objects.filter(pk=pw.pk)
        topo_filtered = PathwayGraph.build_topology(pathway_qs=qs)
        # Filtered topology has just this one edge
        assert topo_filtered.graph.number_of_edges() == 1
        # And no cache was populated by this call
        assert PathwayGraph._topo_cache is None

    def test_build_topology_junction_edges(self, srid):
        """Conduits with junction endpoints add junction-keyed edges (lines 144-149).

        Topology: S0 --trunk-- S1, with a junction J on the trunk.
        A branch conduit attaches to J via start_junction, ending at S2.
        After build_topology, ('junction', J.pk) is a node and the branch
        edge runs from the junction to ('structure', S2).
        """
        s0 = Structure.objects.create(name="J-s0", location=Point(0, 0, srid=srid))
        s1 = Structure.objects.create(name="J-s1", location=Point(0.02, 0.02, srid=srid))
        s2 = Structure.objects.create(name="J-s2", location=Point(0.03, 0.01, srid=srid))
        trunk = Conduit.objects.create(
            label="J-trunk",
            start_structure=s0,
            end_structure=s1,
            path=LineString((0, 0), (0.02, 0.02), srid=srid),
            length=100,
        )
        branch = Conduit.objects.create(
            label="J-branch-stub",
            start_structure=s2,
            end_structure=s2,  # placeholder; we'll repoint to a junction below
            path=LineString((0.03, 0.01), (0.03, 0.01), srid=srid),
            length=1,
        )
        junction = ConduitJunction.objects.create(
            label="J",
            trunk_conduit=trunk,
            branch_conduit=branch,
            towards_structure=s1,
            position_on_trunk=0.5,
        )
        # Now create the real branch conduit from junction -> s2
        branch_real = Conduit.objects.create(
            label="J-branch",
            start_structure=None,
            start_junction=junction,
            end_structure=s2,
            path=LineString((0.01, 0.01), (0.03, 0.01), srid=srid),
            length=20,
        )

        topo = PathwayGraph.build_topology()
        assert ("junction", junction.pk) in topo.graph
        # Junction-to-structure edge exists with our branch_real's pk
        edge = topo.graph.edges[("junction", junction.pk), ("structure", s2.pk)]
        assert edge["pathway_id"] == branch_real.pathway_ptr_id


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConnectedPathwaysDb:
    @pytest.fixture
    def srid(self):
        return get_srid()

    def test_structure_node(self, srid):
        """connected_pathways_db filters by structure on either end (line 392)."""
        s1 = Structure.objects.create(name="cpd-s1", location=Point(0, 0, srid=srid))
        s2 = Structure.objects.create(name="cpd-s2", location=Point(0.01, 0.01, srid=srid))
        s3 = Structure.objects.create(name="cpd-s3", location=Point(0.02, 0.02, srid=srid))
        pw_in = Pathway.objects.create(
            label="cpd-in",
            pathway_type="conduit",
            path=LineString((0, 0), (0.01, 0.01), srid=srid),
            start_structure=s1,
            end_structure=s2,
        )
        pw_out = Pathway.objects.create(
            label="cpd-out",
            pathway_type="conduit",
            path=LineString((0.01, 0.01), (0.02, 0.02), srid=srid),
            start_structure=s2,
            end_structure=s3,
        )
        result = list(connected_pathways_db(("structure", s2.pk)))
        pks = {p.pk for p in result}
        assert pw_in.pk in pks
        assert pw_out.pk in pks

    def test_location_node(self, srid):
        """connected_pathways_db handles location nodes (line 394)."""
        from dcim.models import Location, Site

        site = Site.objects.create(name="cpd-site", slug="cpd-site")
        loc = Location.objects.create(name="cpd-loc", slug="cpd-loc", site=site)
        s = Structure.objects.create(name="cpd-loc-s", location=Point(0, 0, srid=srid))
        pw = Pathway.objects.create(
            label="cpd-loc-pw",
            pathway_type="conduit",
            path=LineString((0, 0), (0.01, 0.01), srid=srid),
            start_structure=s,
            end_location=loc,
        )
        result = list(connected_pathways_db(("location", loc.pk)))
        assert pw in result

    def test_junction_node(self, srid):
        """connected_pathways_db handles junction nodes (line 396)."""
        s0 = Structure.objects.create(name="cpd-j0", location=Point(0, 0, srid=srid))
        s1 = Structure.objects.create(name="cpd-j1", location=Point(0.02, 0.02, srid=srid))
        s2 = Structure.objects.create(name="cpd-j2", location=Point(0.03, 0.01, srid=srid))
        trunk = Conduit.objects.create(
            label="cpd-trunk",
            start_structure=s0,
            end_structure=s1,
            path=LineString((0, 0), (0.02, 0.02), srid=srid),
            length=50,
        )
        stub = Conduit.objects.create(
            label="cpd-stub",
            start_structure=s2,
            end_structure=s2,
            path=LineString((0.03, 0.01), (0.03, 0.01), srid=srid),
            length=1,
        )
        junction = ConduitJunction.objects.create(
            label="cpd-J",
            trunk_conduit=trunk,
            branch_conduit=stub,
            towards_structure=s1,
            position_on_trunk=0.5,
        )
        branch = Conduit.objects.create(
            label="cpd-branch",
            start_junction=junction,
            end_structure=s2,
            path=LineString((0.01, 0.01), (0.03, 0.01), srid=srid),
            length=20,
        )
        result = list(connected_pathways_db(("junction", junction.pk)))
        # Branch attaches to the junction directly
        assert any(p.pk == branch.pathway_ptr_id for p in result)

    def test_unknown_node_type_returns_empty(self):
        """Unknown node kind returns an empty queryset (line 398)."""
        result = connected_pathways_db(("bogus", 1))
        assert list(result) == []


@pytest.mark.django_db
class TestTraceCable:
    @pytest.fixture
    def srid(self):
        return get_srid()

    @pytest.fixture(autouse=True)
    def _disable_routability_signal(self):
        from django.db.models.signals import pre_save

        from netbox_pathways.signals import enforce_cable_routability

        pre_save.disconnect(enforce_cable_routability, sender=CableSegment)
        yield
        pre_save.connect(enforce_cable_routability, sender=CableSegment)

    def test_returns_segments_in_sequence(self, srid):
        """trace_cable orders segments by sequence and exposes pathway metadata."""
        from dcim.models import Cable

        s1 = Structure.objects.create(name="tc-s1", location=Point(0, 0, srid=srid))
        s2 = Structure.objects.create(name="tc-s2", location=Point(0.01, 0.01, srid=srid))
        s3 = Structure.objects.create(name="tc-s3", location=Point(0.02, 0.02, srid=srid))
        pw1 = Pathway.objects.create(
            label="tc-pw1",
            pathway_type="conduit",
            path=LineString((0, 0), (0.01, 0.01), srid=srid),
            start_structure=s1,
            end_structure=s2,
            length=10,
        )
        pw2 = Pathway.objects.create(
            label="tc-pw2",
            pathway_type="conduit",
            path=LineString((0.01, 0.01), (0.02, 0.02), srid=srid),
            start_structure=s2,
            end_structure=s3,
            length=20,
        )
        cable = Cable.objects.create(label="tc-cable")
        # Create segments out of sequence to confirm ordering
        CableSegment.objects.create(cable=cable, pathway=pw2, sequence=2)
        CableSegment.objects.create(cable=cable, pathway=pw1, sequence=1)

        result = trace_cable(cable.pk)
        assert [r["pathway_id"] for r in result] == [pw1.pk, pw2.pk]
        # Each entry exposes coords (LineString -> list of coord pairs)
        assert result[0]["pathway_type"] == "conduit"
        assert result[0]["length"] == 10
        assert len(result[0]["coords"]) == 2
        # Endpoint names resolve via the pathway's start/end endpoints
        assert result[0]["start_name"] == str(s1)
        assert result[0]["end_name"] == str(s2)

    def test_segment_without_pathway_yields_null_fields(self, srid):
        """A segment whose pathway was deleted (SET_NULL) still appears with null fields."""
        from dcim.models import Cable

        s1 = Structure.objects.create(name="tc-null-s1", location=Point(0, 0, srid=srid))
        s2 = Structure.objects.create(name="tc-null-s2", location=Point(0.01, 0.01, srid=srid))
        pw = Pathway.objects.create(
            label="tc-null-pw",
            pathway_type="conduit",
            path=LineString((0, 0), (0.01, 0.01), srid=srid),
            start_structure=s1,
            end_structure=s2,
            length=10,
        )
        cable = Cable.objects.create(label="tc-null-cable")
        CableSegment.objects.create(cable=cable, pathway=pw, sequence=1)
        pw.delete()  # SET_NULL on pathway FK

        result = trace_cable(cable.pk)
        assert len(result) == 1
        entry = result[0]
        assert entry["pathway_id"] is None
        assert entry["pathway_name"] is None
        assert entry["coords"] == []
        assert entry["start_name"] is None
        assert entry["end_name"] is None


@pytest.mark.django_db
class TestBatchResolveNodes:
    @pytest.fixture
    def srid(self):
        return get_srid()

    def test_resolves_structure_label_and_geo(self, srid):
        s = Structure.objects.create(name="brn-s", location=Point(1.5, 2.5, srid=srid))
        resolved = batch_resolve_nodes([("structure", s.pk)])
        entry = resolved[("structure", s.pk)]
        assert entry["label"] == str(s)
        assert entry["geo"] is not None  # (lat, lon)

    def test_missing_structure_falls_back_to_placeholder_label(self):
        resolved = batch_resolve_nodes([("structure", 9999999)])
        assert resolved[("structure", 9999999)]["label"] == "Structure #9999999"
        assert resolved[("structure", 9999999)]["geo"] is None

    def test_resolves_location_label(self, srid):
        from dcim.models import Location, Site

        site = Site.objects.create(name="brn-site", slug="brn-site")
        loc = Location.objects.create(name="brn-loc", slug="brn-loc", site=site)
        resolved = batch_resolve_nodes([("location", loc.pk)])
        entry = resolved[("location", loc.pk)]
        assert entry["label"] == str(loc)
        # Locations do not carry geo through this helper
        assert entry["geo"] is None

    def test_missing_location_falls_back_to_placeholder_label(self):
        resolved = batch_resolve_nodes([("location", 9999999)])
        assert resolved[("location", 9999999)]["label"] == "Location #9999999"

    # NOTE: junction resolution via batch_resolve_nodes is not testable until the
    # source bug in graph._batch_fetch_junctions is fixed -- it calls
    # `.only("name", "trunk_conduit__name", ...)` but ConduitJunction and Pathway
    # both use `label`, not `name`, so the query raises FieldDoesNotExist on eval.

    def test_node_to_label_single_node_convenience(self, srid):
        s = Structure.objects.create(name="ntl-s", location=Point(0, 0, srid=srid))
        assert node_to_label(("structure", s.pk)) == str(s)

    def test_node_to_geo_single_node_convenience(self, srid):
        s = Structure.objects.create(name="ntg-s", location=Point(1, 2, srid=srid))
        geo = node_to_geo(("structure", s.pk))
        assert geo is not None
        lat, lon = geo
        # Sanity: WGS84 lat/lon range
        assert -90 <= lat <= 90
        assert -180 <= lon <= 180

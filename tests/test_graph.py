import pytest
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.geo import get_srid
from netbox_pathways.graph import PathwayGraph
from netbox_pathways.models import Conduit, Structure


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
                name=f"G-{i}", location=Point(i * 0.01, i * 0.01, srid=srid),
            )
            for i in range(4)
        ]

    @pytest.fixture
    def pathways(self, structures, srid):
        """Create conduits: S0-S1 (10m), S1-S2 (20m), S2-S3 (5m), S0-S3 shortcut (50m)"""
        pws = []
        pairs = [(0, 1, 10), (1, 2, 20), (2, 3, 5), (0, 3, 50)]
        for a, b, length in pairs:
            pws.append(Conduit.objects.create(
                label=f"C-{a}-{b}",
                start_structure=structures[a],
                end_structure=structures[b],
                path=LineString(
                    (a * 0.01, a * 0.01), (b * 0.01, b * 0.01), srid=srid,
                ),
                length=length,
            ))
        return pws

    def test_build_creates_graph(self, pathways):
        graph = PathwayGraph.build()
        assert graph.node_count >= 4
        assert graph.edge_count >= 4

    def test_shortest_path_by_length(self, structures, pathways):
        graph = PathwayGraph.build()
        start = ('structure', structures[0].pk)
        end = ('structure', structures[3].pk)
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
        result = graph.shortest_path(
            ('structure', s1.pk), ('structure', s2.pk)
        )
        assert result is None

    def test_all_routes(self, structures, pathways):
        graph = PathwayGraph.build()
        start = ('structure', structures[0].pk)
        end = ('structure', structures[3].pk)
        routes = graph.all_routes(start, end)
        # Two routes: S0->S1->S2->S3 (35m) and S0->S3 (50m)
        assert len(routes) == 2
        # Sorted by cost
        assert routes[0][0] <= routes[1][0]

    def test_astar_path(self, structures, pathways):
        graph = PathwayGraph.build()
        start = ('structure', structures[0].pk)
        end = ('structure', structures[3].pk)
        result = graph.astar_path(start, end)
        assert result is not None
        cost, path_ids = result
        assert cost == 35

    def test_connected_pathways(self, structures, pathways):
        graph = PathwayGraph.build()
        node = ('structure', structures[0].pk)
        connected = graph.connected_pathways(node)
        # S0 connects to S1 and S3
        assert len(connected) == 2
        dest_nodes = {c['destination'] for c in connected}
        assert ('structure', structures[1].pk) in dest_nodes
        assert ('structure', structures[3].pk) in dest_nodes

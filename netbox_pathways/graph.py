"""
Graph traversal algorithms for the pathway network.

Nodes: ('structure', pk), ('location', pk), ('junction', pk) tuples.
Edges: Pathway instances connecting endpoints, weighted by length.
"""

import heapq
from collections import defaultdict

from django.db.models import Q, Subquery, OuterRef

from . import models


def _endpoint_nodes(pathway):
    """Return (start_node, end_node) tuples for a pathway."""
    start = None
    end = None

    if pathway.start_structure_id:
        start = ('structure', pathway.start_structure_id)
    elif pathway.start_location_id:
        start = ('location', pathway.start_location_id)

    if pathway.end_structure_id:
        end = ('structure', pathway.end_structure_id)
    elif pathway.end_location_id:
        end = ('location', pathway.end_location_id)

    # Conduit junction endpoints (accessed via LEFT JOIN annotation)
    start_junc = getattr(pathway, '_start_junction_id', None)
    end_junc = getattr(pathway, '_end_junction_id', None)
    if start_junc:
        start = ('junction', start_junc)
    if end_junc:
        end = ('junction', end_junc)

    return start, end


class PathwayGraph:
    """In-memory adjacency list built from Pathway queryset."""

    def __init__(self):
        self.adj = defaultdict(list)  # node -> [(neighbor, pathway_id, weight)]
        self.pathways = {}  # pathway_id -> {id, name, type, length, path_coords}

    @classmethod
    def build(cls, site_id=None):
        """
        Build graph from all pathways. Optionally scope to a site.
        """
        graph = cls()

        qs = models.Pathway.objects.select_related(
            'start_structure', 'end_structure',
            'start_location', 'end_location',
        ).only(
            'id', 'name', 'pathway_type', 'path', 'length',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
        )

        if site_id:
            qs = qs.filter(
                Q(start_structure__site_id=site_id) | Q(end_structure__site_id=site_id)
            )

        # LEFT JOIN to conduit for junction fields
        conduit_qs = models.Conduit.objects.filter(pathway_ptr_id=OuterRef('pk'))
        qs = qs.annotate(
            _start_junction_id=Subquery(conduit_qs.values('start_junction_id')[:1]),
            _end_junction_id=Subquery(conduit_qs.values('end_junction_id')[:1]),
        )

        for pw in qs:
            start, end = _endpoint_nodes(pw)
            if not start or not end or start == end:
                continue

            weight = pw.length or 0
            coords = [[p[0], p[1]] for p in pw.path.coords] if pw.path else []

            graph.pathways[pw.pk] = {
                'id': pw.pk,
                'name': pw.name,
                'pathway_type': pw.pathway_type,
                'length': weight,
                'coords': coords,
                'url': pw.get_absolute_url(),
            }

            graph.adj[start].append((end, pw.pk, weight))
            graph.adj[end].append((start, pw.pk, weight))

        return graph

    def shortest_path(self, start_node, end_node):
        """
        Dijkstra's algorithm. Returns (total_cost, [pathway_ids]) or None.
        """
        if start_node not in self.adj or end_node not in self.adj:
            return None

        dist = {start_node: 0}
        prev = {}  # node -> (prev_node, pathway_id)
        heap = [(0, start_node)]

        while heap:
            cost, node = heapq.heappop(heap)
            if node == end_node:
                # Reconstruct path
                path_ids = []
                cur = end_node
                while cur in prev:
                    prev_node, pw_id = prev[cur]
                    path_ids.append(pw_id)
                    cur = prev_node
                path_ids.reverse()
                return cost, path_ids

            if cost > dist.get(node, float('inf')):
                continue

            for neighbor, pw_id, weight in self.adj[node]:
                new_cost = cost + weight
                if new_cost < dist.get(neighbor, float('inf')):
                    dist[neighbor] = new_cost
                    prev[neighbor] = (node, pw_id)
                    heapq.heappush(heap, (new_cost, neighbor))

        return None

    def all_routes(self, start_node, end_node, max_depth=20, max_routes=10):
        """
        BFS/DFS to find all simple routes between two nodes.
        Returns list of (total_cost, [pathway_ids]).
        """
        if start_node not in self.adj or end_node not in self.adj:
            return []

        results = []
        # Stack: (current_node, visited_nodes, path_ids, total_cost)
        stack = [(start_node, {start_node}, [], 0)]

        while stack and len(results) < max_routes:
            node, visited, path_ids, cost = stack.pop()

            if node == end_node and path_ids:
                results.append((cost, list(path_ids)))
                continue

            if len(path_ids) >= max_depth:
                continue

            for neighbor, pw_id, weight in self.adj[node]:
                if neighbor not in visited:
                    new_visited = visited | {neighbor}
                    stack.append((
                        neighbor,
                        new_visited,
                        path_ids + [pw_id],
                        cost + weight,
                    ))

        results.sort(key=lambda r: r[0])
        return results

    def neighbors(self, start_node, max_hops=3):
        """
        BFS to find all reachable structures within max_hops.
        Returns dict: node -> (distance, hops, [pathway_ids_to_reach]).
        """
        if start_node not in self.adj:
            return {}

        result = {}
        # (node, hops, distance, path_ids)
        queue = [(start_node, 0, 0, [])]
        visited = {start_node}

        while queue:
            node, hops, dist, path_ids = queue.pop(0)

            if node != start_node:
                result[node] = (dist, hops, path_ids)

            if hops >= max_hops:
                continue

            for neighbor, pw_id, weight in self.adj[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((
                        neighbor,
                        hops + 1,
                        dist + weight,
                        path_ids + [pw_id],
                    ))

        return result


def trace_cable(cable_id):
    """
    Trace a cable's physical route through pathways via CableSegments.
    Returns list of segment dicts with pathway geo data.
    """
    segments = (
        models.CableSegment.objects
        .filter(cable_id=cable_id)
        .select_related(
            'pathway',
            'pathway__start_structure',
            'pathway__end_structure',
        )
        .order_by('sequence')
    )

    result = []
    for seg in segments:
        pw = seg.pathway
        entry = {
            'segment_id': seg.pk,
            'sequence': seg.sequence,
            'pathway_id': pw.pk if pw else None,
            'pathway_name': pw.name if pw else None,
            'pathway_type': pw.pathway_type if pw else None,
            'pathway_url': pw.get_absolute_url() if pw else None,
            'length': pw.length if pw else None,
            'coords': [],
            'start_name': str(pw.start_endpoint) if pw and pw.start_endpoint else None,
            'end_name': str(pw.end_endpoint) if pw and pw.end_endpoint else None,
        }
        if pw and pw.path:
            entry['coords'] = [[p[0], p[1]] for p in pw.path.coords]
        result.append(entry)

    return result


def node_to_label(node):
    """Convert a node tuple to a human-readable label."""
    kind, pk = node
    if kind == 'structure':
        try:
            return str(models.Structure.objects.get(pk=pk))
        except models.Structure.DoesNotExist:
            return f'Structure #{pk}'
    elif kind == 'location':
        from dcim.models import Location
        try:
            return str(Location.objects.get(pk=pk))
        except Location.DoesNotExist:
            return f'Location #{pk}'
    elif kind == 'junction':
        try:
            return str(models.ConduitJunction.objects.get(pk=pk))
        except models.ConduitJunction.DoesNotExist:
            return f'Junction #{pk}'
    return str(node)


def node_to_geo(node):
    """Return (lat, lon) for a node, or None."""
    kind, pk = node
    if kind == 'structure':
        try:
            s = models.Structure.objects.only('location').get(pk=pk)
            if s.location:
                return (s.location.y, s.location.x)
        except models.Structure.DoesNotExist:
            pass
    elif kind == 'junction':
        try:
            j = models.ConduitJunction.objects.select_related('trunk_conduit').get(pk=pk)
            loc = j.location
            if loc:
                return (loc.y, loc.x)
        except models.ConduitJunction.DoesNotExist:
            pass
    return None

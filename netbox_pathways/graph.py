"""
Graph traversal algorithms for the pathway network.

Nodes: ('structure', pk), ('location', pk), ('junction', pk) tuples.
Edges: Pathway instances connecting endpoints, weighted by length.
"""

import math

import networkx as nx
from django.db.models import OuterRef, Q, Subquery

from . import models
from .geo import linestring_to_coords, point_to_latlon


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
    """NetworkX-backed graph of the pathway network."""

    def __init__(self):
        self.graph = nx.Graph()
        self.pathways = {}  # pathway_id -> {id, name, type, length, coords, url}

    @property
    def node_count(self):
        return self.graph.number_of_nodes()

    @property
    def edge_count(self):
        return self.graph.number_of_edges()

    @classmethod
    def build(cls, site_id=None):
        """Build full graph with pathway metadata (for display).

        Prefer build_topology() for route-finding — it's 10-100x faster
        because it skips per-row serialization.
        """
        instance = cls._build_base(site_id=site_id, include_metadata=True)
        return instance

    # Module-level topology cache
    _topo_cache = None
    _topo_cache_time = 0
    _TOPO_TTL = 300  # seconds

    @classmethod
    def build_topology(cls):
        """Build lightweight graph for route-finding only.

        Uses values_list() to skip ORM model instantiation entirely.
        Cached for 5 minutes — subsequent calls are instant.
        """
        import time

        now = time.time()
        if cls._topo_cache and (now - cls._topo_cache_time) < cls._TOPO_TTL:
            return cls._topo_cache

        instance = cls()

        # Fast path: raw tuples, no model instances, no joins for geo
        rows = (
            models.Pathway.objects
            .exclude(start_structure__isnull=True, start_location__isnull=True)
            .exclude(end_structure__isnull=True, end_location__isnull=True)
            .values_list(
                'pk', 'length', 'pathway_type',
                'start_structure_id', 'end_structure_id',
                'start_location_id', 'end_location_id',
            )
        )

        for pk, length, pw_type, ss_id, es_id, sl_id, el_id in rows.iterator():
            start = None
            end = None
            if ss_id:
                start = ('structure', ss_id)
            elif sl_id:
                start = ('location', sl_id)
            if es_id:
                end = ('structure', es_id)
            elif el_id:
                end = ('location', el_id)

            if not start or not end or start == end:
                continue

            instance.graph.add_edge(
                start, end,
                pathway_id=pk,
                weight=length or 0,
                pathway_type=pw_type,
            )

        # Add junction-based edges (conduits with junctions)
        junction_rows = (
            models.Conduit.objects
            .exclude(start_junction__isnull=True, end_junction__isnull=True)
            .values_list(
                'pathway_ptr_id', 'length', 'pathway_type',
                'start_structure_id', 'end_structure_id',
                'start_junction_id', 'end_junction_id',
            )
        )
        for pk, length, pw_type, ss_id, es_id, sj_id, ej_id in junction_rows.iterator():
            start = ('junction', sj_id) if sj_id else (('structure', ss_id) if ss_id else None)
            end = ('junction', ej_id) if ej_id else (('structure', es_id) if es_id else None)
            if not start or not end or start == end:
                continue
            # Override the edge from the first pass if junction is more specific
            instance.graph.add_edge(
                start, end,
                pathway_id=pk,
                weight=length or 0,
                pathway_type=pw_type,
            )

        # Skip geo coordinates — Dijkstra is fast enough on this graph size
        # (2ms on 37k edges). A* heuristic would require 30k coordinate
        # transforms which takes longer than the Dijkstra itself.

        cls._topo_cache = instance
        cls._topo_cache_time = now
        return instance

    @classmethod
    def _build_base(cls, site_id=None, include_metadata=True):
        instance = cls()

        qs = models.Pathway.objects.select_related(
            'start_structure', 'end_structure',
            'start_location', 'end_location',
        ).only(
            'id', 'label', 'pathway_type', 'length',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            *(['path'] if include_metadata else []),
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

        for pw in qs.iterator():
            start, end = _endpoint_nodes(pw)
            if not start or not end or start == end:
                continue

            weight = pw.length or 0

            if include_metadata:
                coords = linestring_to_coords(pw.path)
                instance.pathways[pw.pk] = {
                    'id': pw.pk,
                    'name': str(pw),
                    'pathway_type': pw.pathway_type,
                    'length': weight,
                    'coords': coords,
                    'url': pw.get_absolute_url(),
                }

            # Store geo for A* heuristic on structure nodes
            for node in (start, end):
                if node not in instance.graph and node[0] == 'structure':
                    geo = None
                    if node == start and pw.start_structure:
                        geo = point_to_latlon(pw.start_structure.centroid)
                    elif node == end and pw.end_structure:
                        geo = point_to_latlon(pw.end_structure.centroid)
                    instance.graph.add_node(node, geo=geo)

            instance.graph.add_edge(
                start, end,
                pathway_id=pw.pk,
                weight=weight,
                pathway_type=pw.pathway_type,
            )

        return instance

    def shortest_path(self, start_node, end_node):
        """Dijkstra shortest path. Returns (total_cost, [pathway_ids]) or None."""
        try:
            path_nodes = nx.shortest_path(
                self.graph, start_node, end_node, weight='weight',
            )
        except (nx.NodeNotFound, nx.NetworkXNoPath):
            return None
        return self._extract_route(path_nodes)

    def astar_path(self, start_node, end_node):
        """A* shortest path with haversine heuristic. Returns (total_cost, [pathway_ids]) or None."""
        try:
            path_nodes = nx.astar_path(
                self.graph, start_node, end_node,
                heuristic=self._haversine_heuristic,
                weight='weight',
            )
        except (nx.NodeNotFound, nx.NetworkXNoPath):
            return None
        return self._extract_route(path_nodes)

    def all_routes(self, start_node, end_node, max_depth=20, max_routes=10):
        """Find all simple routes. Returns list of (total_cost, [pathway_ids])."""
        if start_node not in self.graph or end_node not in self.graph:
            return []

        results = []
        for path_nodes in nx.all_simple_paths(
            self.graph, start_node, end_node, cutoff=max_depth,
        ):
            route = self._extract_route(path_nodes)
            if route:
                results.append(route)
            if len(results) >= max_routes:
                break

        results.sort(key=lambda r: r[0])
        return results

    def connected_pathways(self, node):
        """Return all pathways connected to a node."""
        if node not in self.graph:
            return []

        result = []
        for neighbor in self.graph.neighbors(node):
            edge_data = self.graph.edges[node, neighbor]
            result.append({
                'pathway_id': edge_data['pathway_id'],
                'destination': neighbor,
                'weight': edge_data.get('weight', 0),
                'pathway_type': edge_data.get('pathway_type', ''),
            })
        return result

    def neighbors(self, start_node, max_hops=3):
        """
        BFS to find all reachable structures within max_hops.
        Returns dict: node -> (distance, hops, [pathway_ids_to_reach]).
        """
        if start_node not in self.graph:
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

            for neighbor in self.graph.neighbors(node):
                if neighbor not in visited:
                    visited.add(neighbor)
                    edge = self.graph.edges[node, neighbor]
                    queue.append((
                        neighbor,
                        hops + 1,
                        dist + edge.get('weight', 0),
                        path_ids + [edge['pathway_id']],
                    ))

        return result

    def _extract_route(self, path_nodes):
        """Convert a list of nodes to (total_cost, [pathway_ids])."""
        path_ids = []
        total_cost = 0
        for i in range(len(path_nodes) - 1):
            edge = self.graph.edges[path_nodes[i], path_nodes[i + 1]]
            path_ids.append(edge['pathway_id'])
            total_cost += edge.get('weight', 0)
        return total_cost, path_ids

    def _haversine_heuristic(self, u, v):
        """Haversine distance in meters between two nodes. Returns 0 if geo unknown."""
        u_geo = self.graph.nodes[u].get('geo') if u in self.graph else None
        v_geo = self.graph.nodes[v].get('geo') if v in self.graph else None
        if not u_geo or not v_geo:
            return 0
        lat1, lon1 = math.radians(u_geo[0]), math.radians(u_geo[1])
        lat2, lon2 = math.radians(v_geo[0]), math.radians(v_geo[1])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 6371000 * 2 * math.asin(math.sqrt(a))


def connected_pathways_db(node):
    """Query pathways connected to a node directly from the database.

    Much faster than building the full graph when you only need adjacency
    for a single node (e.g., "Add Segment" dropdown).
    """
    node_type, node_pk = node
    q = Q()
    if node_type == 'structure':
        q = Q(start_structure_id=node_pk) | Q(end_structure_id=node_pk)
    elif node_type == 'location':
        q = Q(start_location_id=node_pk) | Q(end_location_id=node_pk)
    elif node_type == 'junction':
        q = (
            Q(conduit__start_junction_id=node_pk)
            | Q(conduit__end_junction_id=node_pk)
        )
    else:
        return models.Pathway.objects.none()

    return models.Pathway.objects.filter(q).select_related(
        'start_structure', 'end_structure',
        'start_location', 'end_location',
    ).distinct()


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
            'pathway__start_location',
            'pathway__end_location',
        )
        .order_by('sequence')
    )

    result = []
    for seg in segments:
        pw = seg.pathway
        entry = {
            'segment_id': seg.pk,
            'pathway_id': pw.pk if pw else None,
            'pathway_name': str(pw) if pw else None,
            'pathway_type': pw.pathway_type if pw else None,
            'pathway_url': pw.get_absolute_url() if pw else None,
            'length': pw.length if pw else None,
            'coords': [],
            'start_name': str(pw.start_endpoint) if pw and pw.start_endpoint else None,
            'end_name': str(pw.end_endpoint) if pw and pw.end_endpoint else None,
        }
        if pw and pw.path:
            entry['coords'] = linestring_to_coords(pw.path)
        result.append(entry)

    return result


# --- Batch node resolution helpers ---

def _batch_fetch_structures(pks):
    """Fetch structures by PK set, return dict pk -> Structure."""
    if not pks:
        return {}
    return models.Structure.objects.only(
        'id', 'name', 'structure_type', 'location',
    ).in_bulk(list(pks))


def _batch_fetch_locations(pks):
    """Fetch locations by PK set, return dict pk -> Location."""
    if not pks:
        return {}
    from dcim.models import Location
    return Location.objects.in_bulk(list(pks))


def _batch_fetch_junctions(pks):
    """Fetch junctions by PK set, return dict pk -> ConduitJunction."""
    if not pks:
        return {}
    return models.ConduitJunction.objects.select_related(
        'trunk_conduit',
    ).only(
        'id', 'name', 'trunk_conduit__name', 'trunk_conduit__path',
        'position_on_trunk',
    ).in_bulk(list(pks))


def batch_resolve_nodes(nodes):
    """
    Batch-fetch labels and geo for a collection of node tuples.

    Returns dict: node -> {'label': str, 'geo': (lat, lon) | None}
    """
    structure_pks = {pk for kind, pk in nodes if kind == 'structure'}
    location_pks = {pk for kind, pk in nodes if kind == 'location'}
    junction_pks = {pk for kind, pk in nodes if kind == 'junction'}

    structures = _batch_fetch_structures(structure_pks)
    locations = _batch_fetch_locations(location_pks)
    junctions = _batch_fetch_junctions(junction_pks)

    result = {}
    for node in nodes:
        kind, pk = node
        label = str(node)
        geo = None

        if kind == 'structure':
            s = structures.get(pk)
            if s:
                label = str(s)
                geo = point_to_latlon(s.centroid)
            else:
                label = f'Structure #{pk}'
        elif kind == 'location':
            loc = locations.get(pk)
            if loc:
                label = str(loc)
            else:
                label = f'Location #{pk}'
        elif kind == 'junction':
            j = junctions.get(pk)
            if j:
                label = str(j)
                geo = point_to_latlon(j.location)
            else:
                label = f'Junction #{pk}'

        result[node] = {'label': label, 'geo': geo}
    return result


def node_to_label(node):
    """Convert a node tuple to a human-readable label (single-node convenience)."""
    return batch_resolve_nodes([node])[node]['label']


def node_to_geo(node):
    """Return (lat, lon) for a node in WGS84, or None (single-node convenience)."""
    return batch_resolve_nodes([node])[node]['geo']

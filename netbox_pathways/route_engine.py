"""
Constraint-based route finding engine.

Applies hard constraints at the queryset level (fast, SQL-backed),
then soft constraints as graph weight modifications, then runs
Dijkstra. Supports waypoints via chained shortest paths.
"""

from django.db.models import Q

from . import models
from .graph import PathwayGraph


def find_route(
    start_node,
    end_node,
    # Hard constraints (queryset-level)
    avoid_pathway_types=None,
    avoid_structure_types=None,
    avoid_tenants=None,
    tenant_only=None,
    include_inactive=False,
    # Graph-level constraints
    avoid_structures=None,
    avoid_cables=None,
    avoid_circuits=None,
    avoid_circuit_geometries=None,
    must_pass_through=None,
    # Soft constraints
    prefer_in_use_factor=0,
):
    """
    Find the shortest route between two nodes with constraints.

    Hard constraints (queryset-level, applied as SQL filters):
        avoid_pathway_types: list of pathway_type values to exclude
        avoid_structure_types: list of structure_type values to exclude
        avoid_tenants: list of Tenant instances/PKs to exclude
        tenant_only: single Tenant — only include pathways owned by this tenant (or unassigned)
        include_inactive: if False (default), exclude pathways touching retired/decommissioning structures

    Graph-level constraints (applied after graph construction):
        avoid_structures: list of Structure PKs — remove these nodes entirely
        avoid_cables: list of Cable PKs — remove edges carrying these cables
        avoid_circuits: list of Circuit PKs — remove edges carrying these circuits
        avoid_circuit_geometries: list of CircuitGeometry PKs — remove edges for these
        must_pass_through: list of Structure PKs — route must visit these in order

    Soft constraints (weight modifiers):
        prefer_in_use_factor: 0-100 — how much to prefer pathways already carrying cables
            (0 = no preference, 100 = strongly prefer shared pathways)

    Returns (total_cost, [pathway_ids]) or None if no route exists.
    """
    qs = _build_filtered_queryset(
        avoid_pathway_types=avoid_pathway_types,
        avoid_structure_types=avoid_structure_types,
        avoid_tenants=avoid_tenants,
        tenant_only=tenant_only,
        include_inactive=include_inactive,
    )

    has_constraints = any([
        avoid_pathway_types, avoid_structure_types,
        avoid_tenants, tenant_only, not include_inactive,
    ])
    if has_constraints:
        graph = PathwayGraph.build_topology(pathway_qs=qs)
    else:
        graph = PathwayGraph.build_topology()

    _apply_graph_constraints(
        graph,
        avoid_structures=avoid_structures,
        avoid_cables=avoid_cables,
        avoid_circuits=avoid_circuits,
        avoid_circuit_geometries=avoid_circuit_geometries,
    )

    if prefer_in_use_factor > 0:
        _apply_in_use_preference(graph, prefer_in_use_factor)

    if must_pass_through:
        return _chained_shortest_path(graph, start_node, end_node, must_pass_through)

    return graph.shortest_path(start_node, end_node)


def _build_filtered_queryset(
    avoid_pathway_types=None,
    avoid_structure_types=None,
    avoid_tenants=None,
    tenant_only=None,
    include_inactive=False,
):
    """Build a Pathway queryset with hard constraints applied as SQL filters."""
    qs = models.Pathway.objects.exclude(pathway_type='conduit_bank')

    if not include_inactive:
        inactive = ['retired', 'decommissioning']
        qs = qs.exclude(start_structure__status__in=inactive)
        qs = qs.exclude(end_structure__status__in=inactive)

    if avoid_pathway_types:
        qs = qs.exclude(pathway_type__in=avoid_pathway_types)

    if avoid_structure_types:
        qs = qs.exclude(start_structure__structure_type__in=avoid_structure_types)
        qs = qs.exclude(end_structure__structure_type__in=avoid_structure_types)

    if avoid_tenants:
        qs = qs.exclude(tenant__in=avoid_tenants)

    if tenant_only:
        qs = qs.filter(Q(tenant=tenant_only) | Q(tenant__isnull=True))

    return qs


def _apply_graph_constraints(
    graph,
    avoid_structures=None,
    avoid_cables=None,
    avoid_circuits=None,
    avoid_circuit_geometries=None,
):
    """Remove nodes/edges from the graph based on post-build constraints."""
    if avoid_structures:
        for pk in avoid_structures:
            node = ('structure', pk)
            if node in graph.graph:
                graph.graph.remove_node(node)

    if avoid_cables:
        pathway_ids_to_remove = set(
            models.CableSegment.objects.filter(
                cable_id__in=avoid_cables,
            ).values_list('pathway_id', flat=True)
        )
        edges_to_remove = [
            (u, v) for u, v, d in graph.graph.edges(data=True)
            if d.get('pathway_id') in pathway_ids_to_remove
        ]
        graph.graph.remove_edges_from(edges_to_remove)

    if avoid_circuits:
        from circuits.models import CircuitTermination
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(CircuitTermination)
        # Find CircuitTermination PKs belonging to the specified circuits
        ct_pks = set(
            CircuitTermination.objects.filter(
                circuit_id__in=avoid_circuits,
            ).values_list('pk', flat=True)
        )
        if ct_pks:
            from dcim.models import CableTermination

            cable_ids = set(
                CableTermination.objects.filter(
                    termination_type=ct,
                    termination_id__in=ct_pks,
                ).values_list('cable_id', flat=True)
            )
            if cable_ids:
                pids = set(
                    models.CableSegment.objects.filter(
                        cable_id__in=cable_ids,
                    ).values_list('pathway_id', flat=True)
                )
                edges_to_remove = [
                    (u, v) for u, v, d in graph.graph.edges(data=True)
                    if d.get('pathway_id') in pids
                ]
                graph.graph.remove_edges_from(edges_to_remove)

    if avoid_circuit_geometries:
        from circuits.models import CircuitTermination
        from django.contrib.contenttypes.models import ContentType

        circuit_ids = set(
            models.CircuitGeometry.objects.filter(
                pk__in=avoid_circuit_geometries,
            ).values_list('circuit_id', flat=True)
        )
        if circuit_ids:
            ct = ContentType.objects.get_for_model(CircuitTermination)
            ct_pks = set(
                CircuitTermination.objects.filter(
                    circuit_id__in=circuit_ids,
                ).values_list('pk', flat=True)
            )
            if ct_pks:
                from dcim.models import CableTermination

                cable_ids = set(
                    CableTermination.objects.filter(
                        termination_type=ct,
                        termination_id__in=ct_pks,
                    ).values_list('cable_id', flat=True)
                )
                if cable_ids:
                    pids = set(
                        models.CableSegment.objects.filter(
                            cable_id__in=cable_ids,
                        ).values_list('pathway_id', flat=True)
                    )
                    edges_to_remove = [
                        (u, v) for u, v, d in graph.graph.edges(data=True)
                        if d.get('pathway_id') in pids
                    ]
                    graph.graph.remove_edges_from(edges_to_remove)


def _apply_in_use_preference(graph, factor):
    """Reduce weights on pathways that already carry cables.

    factor: 0-100 — higher values give more preference to shared pathways.
    At factor=100, in-use edges get 50% weight reduction.
    """
    in_use_ids = set(
        models.CableSegment.objects.values_list('pathway_id', flat=True).distinct()
    )
    for _u, _v, data in graph.graph.edges(data=True):
        if data.get('pathway_id') in in_use_ids:
            data['weight'] *= (1 - factor / 200)


def _chained_shortest_path(graph, start, end, waypoints):
    """Find shortest path through ordered waypoints by chaining segments.

    After each segment, intermediate nodes are removed from the graph so
    later segments cannot revisit them (a route must never cross the same
    structure twice).  Only the upcoming waypoints/endpoint are preserved.
    """
    stops = [start] + [('structure', wp) for wp in waypoints] + [end]
    all_pathway_ids = []
    total_cost = 0

    for i in range(len(stops) - 1):
        result = graph.shortest_path_nodes(stops[i], stops[i + 1])
        if result is None:
            return None
        cost, pathway_ids, path_nodes = result
        total_cost += cost
        all_pathway_ids.extend(pathway_ids)

        # Remove traversed nodes so subsequent segments can't revisit them.
        if i < len(stops) - 2:  # skip cleanup after the last segment
            remaining = set(stops[i + 1:])
            for node in path_nodes:
                if node not in remaining and node in graph.graph:
                    graph.graph.remove_node(node)

    return total_cost, all_pathway_ids

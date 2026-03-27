"""
REST API endpoints for graph traversal operations.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..graph import PathwayGraph, batch_resolve_nodes, node_to_label, trace_cable


class RouteFinderView(APIView):
    """
    Find routes between two structures.

    GET /api/plugins/netbox-pathways/traversal/routes/
        ?start_type=structure&start_id=1&end_type=structure&end_id=2
        &mode=shortest  (or mode=all)
        &max_depth=20&max_routes=10
        &site=<site_id>  (optional, scope graph to site)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_type = request.query_params.get('start_type', 'structure')
        start_id = request.query_params.get('start_id')
        end_type = request.query_params.get('end_type', 'structure')
        end_id = request.query_params.get('end_id')
        mode = request.query_params.get('mode', 'shortest')
        site_id = request.query_params.get('site')

        if not start_id or not end_id:
            return Response(
                {'error': 'start_id and end_id are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            start_id = int(start_id)
            end_id = int(end_id)
        except (TypeError, ValueError):
            return Response(
                {'error': 'start_id and end_id must be integers'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if start_type not in ('structure', 'location', 'junction'):
            return Response(
                {'error': 'start_type must be structure, location, or junction'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if end_type not in ('structure', 'location', 'junction'):
            return Response(
                {'error': 'end_type must be structure, location, or junction'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        start_node = (start_type, start_id)
        end_node = (end_type, end_id)

        site_id_int = None
        if site_id:
            try:
                site_id_int = int(site_id)
            except (TypeError, ValueError):
                pass

        graph = PathwayGraph.build(site_id=site_id_int)

        if mode == 'all':
            try:
                max_depth = min(int(request.query_params.get('max_depth', 20)), 50)
            except (TypeError, ValueError):
                max_depth = 20
            try:
                max_routes = min(int(request.query_params.get('max_routes', 10)), 50)
            except (TypeError, ValueError):
                max_routes = 10
            routes_raw = graph.all_routes(start_node, end_node, max_depth, max_routes)
            routes = []
            for cost, pw_ids in routes_raw:
                routes.append({
                    'total_length': cost,
                    'hop_count': len(pw_ids),
                    'pathways': [graph.pathways[pid] for pid in pw_ids],
                })
            return Response({
                'start': {'type': start_type, 'id': start_id, 'label': node_to_label(start_node)},
                'end': {'type': end_type, 'id': end_id, 'label': node_to_label(end_node)},
                'route_count': len(routes),
                'routes': routes,
            })
        else:
            result = graph.shortest_path(start_node, end_node)
            if result is None:
                return Response({
                    'start': {'type': start_type, 'id': start_id, 'label': node_to_label(start_node)},
                    'end': {'type': end_type, 'id': end_id, 'label': node_to_label(end_node)},
                    'route': None,
                    'message': 'No route found',
                })

            cost, pw_ids = result
            return Response({
                'start': {'type': start_type, 'id': start_id, 'label': node_to_label(start_node)},
                'end': {'type': end_type, 'id': end_id, 'label': node_to_label(end_node)},
                'route': {
                    'total_length': cost,
                    'hop_count': len(pw_ids),
                    'pathways': [graph.pathways[pid] for pid in pw_ids],
                },
            })


class CableTraceView(APIView):
    """
    Trace a cable's physical route through pathways.

    GET /api/plugins/netbox-pathways/traversal/cable-trace/?cable_id=<id>
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cable_id = request.query_params.get('cable_id')
        if not cable_id:
            return Response(
                {'error': 'cable_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            cable_id = int(cable_id)
        except (TypeError, ValueError):
            return Response(
                {'error': 'cable_id must be an integer'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        segments = trace_cable(cable_id)
        total_length = sum(s['length'] or 0 for s in segments)

        return Response({
            'cable_id': cable_id,
            'segment_count': len(segments),
            'total_length': total_length,
            'segments': segments,
        })


class NeighborsView(APIView):
    """
    Find all structures reachable from a given structure within N hops.

    GET /api/plugins/netbox-pathways/traversal/neighbors/
        ?type=structure&id=1&max_hops=3&site=<site_id>
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        node_type = request.query_params.get('type', 'structure')
        node_id = request.query_params.get('id')
        try:
            max_hops = min(int(request.query_params.get('max_hops', 3)), 10)
        except (TypeError, ValueError):
            max_hops = 3
        site_id = request.query_params.get('site')

        if not node_id:
            return Response(
                {'error': 'id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            node_id = int(node_id)
        except (TypeError, ValueError):
            return Response(
                {'error': 'id must be an integer'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if node_type not in ('structure', 'location', 'junction'):
            return Response(
                {'error': 'type must be structure, location, or junction'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        start_node = (node_type, node_id)

        site_id_int = None
        if site_id:
            try:
                site_id_int = int(site_id)
            except (TypeError, ValueError):
                pass

        graph = PathwayGraph.build(site_id=site_id_int)
        neighbors = graph.neighbors(start_node, max_hops=max_hops)

        # Batch-resolve all nodes (start + neighbors) in one round-trip
        all_nodes = [start_node] + list(neighbors.keys())
        resolved = batch_resolve_nodes(all_nodes)

        result_nodes = []
        for node, (dist, hops, pw_ids) in sorted(neighbors.items(), key=lambda x: x[1][1]):
            info = resolved[node]
            entry = {
                'type': node[0],
                'id': node[1],
                'label': info['label'],
                'distance': dist,
                'hops': hops,
                'pathway_ids': pw_ids,
            }
            if info['geo']:
                entry['lat'] = info['geo'][0]
                entry['lon'] = info['geo'][1]
            result_nodes.append(entry)

        start_info = resolved[start_node]

        return Response({
            'origin': {
                'type': node_type,
                'id': node_id,
                'label': start_info['label'],
                'lat': start_info['geo'][0] if start_info['geo'] else None,
                'lon': start_info['geo'][1] if start_info['geo'] else None,
            },
            'max_hops': max_hops,
            'neighbor_count': len(result_nodes),
            'neighbors': result_nodes,
            'pathways': {pid: graph.pathways[pid] for pid in graph.pathways},
        })

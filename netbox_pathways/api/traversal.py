"""
REST API endpoints for graph traversal operations.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..graph import trace_cable


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

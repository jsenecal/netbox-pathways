from netbox.api.serializers import NetBoxModelSerializer
from rest_framework import serializers as drf_serializers

from ..models import (
    AerialSpan,
    CableSegment,
    Conduit,
    ConduitBank,
    ConduitJunction,
    DirectBuried,
    Innerduct,
    Pathway,
    PathwayLocation,
    SiteGeometry,
    Structure,
)


class StructureSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:structure-detail',
    )

    class Meta:
        model = Structure
        fields = [
            'id', 'url', 'display', 'name', 'structure_type', 'site',
            'location', 'elevation', 'installation_date', 'owner',
            'access_notes', 'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display', 'name', 'structure_type')


class ConduitBankSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:conduitbank-detail',
    )

    class Meta:
        model = ConduitBank
        fields = [
            'id', 'url', 'display', 'name', 'structure',
            'configuration', 'total_conduits', 'encasement_type',
            'installation_date', 'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display', 'name')


class PathwaySerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:pathway-detail',
    )
    cables_routed = drf_serializers.IntegerField(read_only=True)

    class Meta:
        model = Pathway
        fields = [
            'id', 'url', 'display', 'name', 'pathway_type', 'path',
            'start_structure', 'end_structure',
            'start_location', 'end_location', 'length',
            'cables_routed', 'installation_date',
            'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display', 'name', 'pathway_type')


class ConduitSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:conduit-detail',
    )
    cables_routed = drf_serializers.IntegerField(read_only=True)

    class Meta:
        model = Conduit
        fields = [
            'id', 'url', 'display', 'name', 'pathway_type', 'path',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            'material', 'inner_diameter', 'outer_diameter', 'depth',
            'conduit_bank', 'bank_position',
            'start_junction', 'end_junction',
            'length', 'cables_routed',
            'installation_date', 'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display', 'name', 'material')


class AerialSpanSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:aerialspan-detail',
    )
    cables_routed = drf_serializers.IntegerField(read_only=True)

    class Meta:
        model = AerialSpan
        fields = [
            'id', 'url', 'display', 'name', 'pathway_type', 'path',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            'aerial_type', 'attachment_height', 'sag',
            'messenger_size', 'wind_loading', 'ice_loading',
            'length', 'cables_routed',
            'installation_date', 'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display', 'name', 'aerial_type')


class DirectBuriedSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:directburied-detail',
    )
    cables_routed = drf_serializers.IntegerField(read_only=True)

    class Meta:
        model = DirectBuried
        fields = [
            'id', 'url', 'display', 'name', 'pathway_type', 'path',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            'burial_depth', 'warning_tape', 'tracer_wire', 'armor_type',
            'length', 'cables_routed',
            'installation_date', 'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display', 'name')


class InnerductSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:innerduct-detail',
    )
    cables_routed = drf_serializers.IntegerField(read_only=True)

    class Meta:
        model = Innerduct
        fields = [
            'id', 'url', 'display', 'name', 'pathway_type', 'path',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            'parent_conduit', 'size', 'color', 'position',
            'length', 'cables_routed',
            'installation_date', 'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display', 'name', 'size')


class ConduitJunctionSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:conduitjunction-detail',
    )

    class Meta:
        model = ConduitJunction
        fields = [
            'id', 'url', 'display', 'name',
            'trunk_conduit', 'branch_conduit',
            'towards_structure', 'position_on_trunk',
            'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display', 'name')


class PathwayLocationSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:pathwaylocation-detail',
    )

    class Meta:
        model = PathwayLocation
        fields = [
            'id', 'url', 'display', 'pathway', 'site', 'location',
            'sequence', 'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display', 'pathway', 'sequence')


class CableSegmentSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:cablesegment-detail',
    )

    class Meta:
        model = CableSegment
        fields = [
            'id', 'url', 'display', 'cable', 'pathway', 'sequence',
            'enter_point', 'exit_point',
            'slack_loop_location', 'slack_length',
            'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display', 'cable', 'sequence')


class SiteGeometrySerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:sitegeometry-detail',
    )

    class Meta:
        model = SiteGeometry
        fields = [
            'id', 'url', 'display', 'site', 'structure', 'geometry',
            'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display', 'site')

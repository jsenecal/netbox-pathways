from circuits.api.serializers_.circuits import CircuitSerializer
from dcim.api.serializers_.cables import CableSerializer
from dcim.api.serializers_.sites import LocationSerializer, SiteSerializer
from netbox.api.fields import ChoiceField
from netbox.api.serializers import NetBoxModelSerializer
from rest_framework import serializers as drf_serializers
from tenancy.api.serializers_.tenants import TenantSerializer

from ..choices import (
    AerialTypeChoices,
    BankFaceChoices,
    ConduitBankConfigChoices,
    ConduitMaterialChoices,
    EncasementTypeChoices,
    PathwayTypeChoices,
    StructureStatusChoices,
    StructureTypeChoices,
)
from ..models import (
    AerialSpan,
    CableSegment,
    CircuitGeometry,
    Conduit,
    ConduitBank,
    ConduitJunction,
    DirectBuried,
    Innerduct,
    Pathway,
    PathwayLocation,
    SiteGeometry,
    SlackLoop,
    Structure,
)


class StructureSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:structure-detail',
    )
    status = ChoiceField(choices=StructureStatusChoices, required=False)
    structure_type = ChoiceField(choices=StructureTypeChoices, required=False, allow_blank=True)
    site = SiteSerializer(nested=True, required=False, allow_null=True)
    tenant = TenantSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = Structure
        fields = [
            'id', 'url', 'display_url', 'display', 'name', 'status', 'structure_type', 'site',
            'location', 'height', 'width', 'length', 'depth', 'elevation',
            'installation_date', 'tenant',
            'access_notes', 'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display_url', 'display', 'label', 'structure_type')


# --- Shared FK field declarations for pathway subtypes ---

def _pathway_fk_fields():
    """Common FK field declarations for all pathway-based serializers."""
    return {
        'start_structure': StructureSerializer(nested=True, required=False, allow_null=True),
        'end_structure': StructureSerializer(nested=True, required=False, allow_null=True),
        'start_location': LocationSerializer(nested=True, required=False, allow_null=True),
        'end_location': LocationSerializer(nested=True, required=False, allow_null=True),
        'tenant': TenantSerializer(nested=True, required=False, allow_null=True),
    }


class ConduitBankSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:conduitbank-detail',
    )
    start_structure = StructureSerializer(nested=True, required=False, allow_null=True)
    end_structure = StructureSerializer(nested=True, required=False, allow_null=True)
    start_face = ChoiceField(choices=BankFaceChoices, required=False, allow_blank=True)
    end_face = ChoiceField(choices=BankFaceChoices, required=False, allow_blank=True)
    configuration = ChoiceField(choices=ConduitBankConfigChoices, required=False, allow_blank=True)
    encasement_type = ChoiceField(choices=EncasementTypeChoices, required=False, allow_blank=True)
    tenant = TenantSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = ConduitBank
        fields = [
            'id', 'url', 'display_url', 'display', 'label',
            'start_structure', 'end_structure', 'start_face', 'end_face',
            'tenant', 'path', 'length',
            'configuration', 'total_conduits', 'encasement_type',
            'installation_date', 'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display_url', 'display', 'label')


class PathwaySerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:pathway-detail',
    )
    pathway_type = ChoiceField(choices=PathwayTypeChoices, required=False, allow_blank=True)
    start_structure = StructureSerializer(nested=True, required=False, allow_null=True)
    end_structure = StructureSerializer(nested=True, required=False, allow_null=True)
    start_location = LocationSerializer(nested=True, required=False, allow_null=True)
    end_location = LocationSerializer(nested=True, required=False, allow_null=True)
    tenant = TenantSerializer(nested=True, required=False, allow_null=True)
    cables_routed = drf_serializers.IntegerField(read_only=True)

    class Meta:
        model = Pathway
        fields = [
            'id', 'url', 'display_url', 'display', 'label', 'pathway_type', 'path',
            'start_structure', 'end_structure',
            'start_location', 'end_location', 'tenant', 'length',
            'cables_routed', 'installation_date',
            'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display_url', 'display', 'label', 'pathway_type')


class ConduitSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:conduit-detail',
    )
    material = ChoiceField(choices=ConduitMaterialChoices, required=False, allow_blank=True)
    start_structure = StructureSerializer(nested=True, required=False, allow_null=True)
    end_structure = StructureSerializer(nested=True, required=False, allow_null=True)
    start_location = LocationSerializer(nested=True, required=False, allow_null=True)
    end_location = LocationSerializer(nested=True, required=False, allow_null=True)
    conduit_bank = ConduitBankSerializer(nested=True, required=False, allow_null=True)
    tenant = TenantSerializer(nested=True, required=False, allow_null=True)
    cables_routed = drf_serializers.IntegerField(read_only=True)

    class Meta:
        model = Conduit
        fields = [
            'id', 'url', 'display_url', 'display', 'label', 'pathway_type', 'path',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            'material', 'inner_diameter', 'outer_diameter', 'depth',
            'conduit_bank', 'bank_position',
            'start_junction', 'end_junction',
            'length', 'cables_routed',
            'installation_date', 'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display_url', 'display', 'label', 'material')


class AerialSpanSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:aerialspan-detail',
    )
    aerial_type = ChoiceField(choices=AerialTypeChoices, required=False, allow_blank=True)
    start_structure = StructureSerializer(nested=True, required=False, allow_null=True)
    end_structure = StructureSerializer(nested=True, required=False, allow_null=True)
    start_location = LocationSerializer(nested=True, required=False, allow_null=True)
    end_location = LocationSerializer(nested=True, required=False, allow_null=True)
    tenant = TenantSerializer(nested=True, required=False, allow_null=True)
    cables_routed = drf_serializers.IntegerField(read_only=True)

    class Meta:
        model = AerialSpan
        fields = [
            'id', 'url', 'display_url', 'display', 'label', 'pathway_type', 'path',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            'aerial_type', 'attachment_height', 'sag',
            'messenger_size', 'wind_loading', 'ice_loading',
            'length', 'cables_routed',
            'installation_date', 'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display_url', 'display', 'label', 'aerial_type')


class DirectBuriedSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:directburied-detail',
    )
    start_structure = StructureSerializer(nested=True, required=False, allow_null=True)
    end_structure = StructureSerializer(nested=True, required=False, allow_null=True)
    start_location = LocationSerializer(nested=True, required=False, allow_null=True)
    end_location = LocationSerializer(nested=True, required=False, allow_null=True)
    tenant = TenantSerializer(nested=True, required=False, allow_null=True)
    cables_routed = drf_serializers.IntegerField(read_only=True)

    class Meta:
        model = DirectBuried
        fields = [
            'id', 'url', 'display_url', 'display', 'label', 'pathway_type', 'path',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            'burial_depth', 'warning_tape', 'tracer_wire', 'armor_type',
            'length', 'cables_routed',
            'installation_date', 'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display_url', 'display', 'label')


class InnerductSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:innerduct-detail',
    )
    start_structure = StructureSerializer(nested=True, required=False, allow_null=True)
    end_structure = StructureSerializer(nested=True, required=False, allow_null=True)
    start_location = LocationSerializer(nested=True, required=False, allow_null=True)
    end_location = LocationSerializer(nested=True, required=False, allow_null=True)
    parent_conduit = ConduitSerializer(nested=True, required=False, allow_null=True)
    cables_routed = drf_serializers.IntegerField(read_only=True)

    class Meta:
        model = Innerduct
        fields = [
            'id', 'url', 'display_url', 'display', 'label', 'pathway_type', 'path',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            'parent_conduit', 'size', 'color', 'position',
            'length', 'cables_routed',
            'installation_date', 'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display_url', 'display', 'label', 'size')


class ConduitJunctionSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:conduitjunction-detail',
    )
    trunk_conduit = ConduitSerializer(nested=True, required=False, allow_null=True)
    branch_conduit = ConduitSerializer(nested=True, required=False, allow_null=True)
    towards_structure = StructureSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = ConduitJunction
        fields = [
            'id', 'url', 'display_url', 'display', 'label',
            'trunk_conduit', 'branch_conduit',
            'towards_structure', 'position_on_trunk',
            'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display_url', 'display', 'label')


class PathwayLocationSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:pathwaylocation-detail',
    )
    pathway = PathwaySerializer(nested=True, required=False, allow_null=True)
    site = SiteSerializer(nested=True, required=False, allow_null=True)
    location = LocationSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = PathwayLocation
        fields = [
            'id', 'url', 'display_url', 'display', 'pathway', 'site', 'location',
            'sequence', 'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display_url', 'display', 'pathway', 'sequence')


class CableSegmentSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:cablesegment-detail',
    )
    cable = CableSerializer(nested=True, required=False, allow_null=True)
    pathway = PathwaySerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = CableSegment
        fields = [
            'id', 'url', 'display_url', 'display', 'cable', 'pathway',
            'sequence',
            'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display_url', 'display', 'cable', 'pathway', 'sequence')


class SlackLoopSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:slackloop-detail',
    )
    cable = CableSerializer(nested=True, required=False, allow_null=True)
    structure = StructureSerializer(nested=True, required=False, allow_null=True)
    pathway = PathwaySerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = SlackLoop
        fields = [
            'id', 'url', 'display_url', 'display', 'cable', 'structure', 'pathway',
            'length', 'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display_url', 'display', 'cable', 'structure', 'length')


class SiteGeometrySerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:sitegeometry-detail',
    )
    site = SiteSerializer(nested=True, required=False, allow_null=True)
    structure = StructureSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = SiteGeometry
        fields = [
            'id', 'url', 'display_url', 'display', 'site', 'structure', 'geometry',
            'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display_url', 'display', 'site')


class CircuitGeometrySerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_pathways-api:circuitgeometry-detail',
    )
    circuit = CircuitSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = CircuitGeometry
        fields = [
            'id', 'url', 'display_url', 'display', 'circuit', 'path',
            'provider_reference', 'comments', 'tags', 'created', 'last_updated',
        ]
        brief_fields = ('id', 'url', 'display_url', 'display', 'circuit')

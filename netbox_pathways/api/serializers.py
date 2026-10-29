from circuits.api.serializers_.circuits import CircuitSerializer
from dcim.api.serializers_.cables import CableSerializer
from dcim.api.serializers_.sites import LocationSerializer, SiteSerializer
from netbox.api.fields import ChoiceField
from netbox.api.serializers import NetBoxModelSerializer, WritableNestedSerializer
from rest_framework import serializers as drf_serializers
from tenancy.api.serializers_.tenants import TenantSerializer

from ..choices import (
    AerialTypeChoices,
    BankFaceChoices,
    ConduitBankConfigChoices,
    ConduitMaterialChoices,
    EncasementTypeChoices,
    PathwayStatusChoices,
    PathwayTypeChoices,
    PlannedRouteStatusChoices,
    StructureStatusChoices,
    StructureTypeChoices,
)
from ..models import (
    CableSegment,
    CircuitGeometry,
    ConduitJunction,
    Pathway,
    PathwayLocation,
    PlannedRoute,
    SiteGeometry,
    Structure,
)
from ..pathway_types import TYPE_SPECIFIC_FIELDS_ORDERED


class StructureSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_pathways-api:structure-detail",
    )
    status = ChoiceField(choices=StructureStatusChoices, required=False)
    structure_type = ChoiceField(choices=StructureTypeChoices, required=False, allow_blank=True)
    site = SiteSerializer(nested=True, required=False, allow_null=True)
    location = LocationSerializer(nested=True, required=False, allow_null=True)
    tenant = TenantSerializer(nested=True, required=False, allow_null=True)
    installed_by = TenantSerializer(nested=True, required=False, allow_null=True)
    no_pathways = drf_serializers.SerializerMethodField(read_only=True)
    description = drf_serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Structure
        fields = [
            "id",
            "url",
            "display_url",
            "display",
            "name",
            "status",
            "structure_type",
            "site",
            "location",
            "geometry",
            "height",
            "width",
            "length",
            "depth",
            "elevation",
            "installation_date",
            "commissioned_date",
            "tenant",
            "installed_by",
            "access_notes",
            "comments",
            "tags",
            "created",
            "last_updated",
            "no_pathways",
            "description",
        ]
        brief_fields = (
            "id",
            "url",
            "display_url",
            "display",
            "label",
            "structure_type",
            "no_pathways",
            "description",
        )

    def get_no_pathways(self, obj):
        if hasattr(obj, "_has_pathways"):
            return not obj._has_pathways
        return None

    def get_description(self, obj):
        if hasattr(obj, "_has_pathways") and not obj._has_pathways:
            return "No connected pathways"
        return None


class PathwayAnchorsMixin(drf_serializers.Serializer):
    """Read-only: the structure each end attaches to.

    The stored anchors -- the end's structure, or the structure enclosing the
    location it names (docs/user-guide/attachment.md).
    """

    start_anchor = StructureSerializer(nested=True, read_only=True)
    end_anchor = StructureSerializer(nested=True, read_only=True)


PATHWAY_BRIEF_FIELDS = ("id", "url", "display_url", "display", "label", "pathway_type")


class NestedPathwaySerializer(WritableNestedSerializer):
    """A pathway's parent: the brief pathway representation, writable by pk."""

    pathway_type = ChoiceField(choices=PathwayTypeChoices, read_only=True)

    class Meta:
        model = Pathway
        fields = PATHWAY_BRIEF_FIELDS


class PathwaySerializer(PathwayAnchorsMixin, NetBoxModelSerializer):
    """Every pathway type through one endpoint.

    Fields that do not apply to the pathway's type are cleared on save, and
    the type rules (containment, required endpoints, geometry) are enforced
    by ``Pathway.clean()``, which NetBox's serializer validation runs.
    """

    url = drf_serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_pathways-api:pathway-detail",
    )
    status = ChoiceField(choices=PathwayStatusChoices, required=False)
    pathway_type = ChoiceField(choices=PathwayTypeChoices)
    parent = NestedPathwaySerializer(required=False, allow_null=True, default=None)
    start_structure = StructureSerializer(nested=True, required=False, allow_null=True)
    end_structure = StructureSerializer(nested=True, required=False, allow_null=True)
    start_location = LocationSerializer(nested=True, required=False, allow_null=True)
    end_location = LocationSerializer(nested=True, required=False, allow_null=True)
    tenant = TenantSerializer(nested=True, required=False, allow_null=True)
    installed_by = TenantSerializer(nested=True, required=False, allow_null=True)
    cables_routed = drf_serializers.IntegerField(read_only=True)
    geo_length = drf_serializers.FloatField(read_only=True)
    start_face = ChoiceField(choices=BankFaceChoices, required=False, allow_blank=True)
    end_face = ChoiceField(choices=BankFaceChoices, required=False, allow_blank=True)
    configuration = ChoiceField(choices=ConduitBankConfigChoices, required=False, allow_blank=True)
    encasement_type = ChoiceField(choices=EncasementTypeChoices, required=False, allow_blank=True)
    material = ChoiceField(choices=ConduitMaterialChoices, required=False, allow_blank=True)
    aerial_type = ChoiceField(choices=AerialTypeChoices, required=False, allow_blank=True)
    attachment_height = drf_serializers.FloatField(read_only=True)

    class Meta:
        model = Pathway
        fields = [
            "id",
            "url",
            "display_url",
            "display",
            "label",
            "status",
            "pathway_type",
            "parent",
            "geometry",
            "start_structure",
            "end_structure",
            "start_location",
            "end_location",
            "start_anchor",
            "end_anchor",
            *TYPE_SPECIFIC_FIELDS_ORDERED,
            "attachment_height",
            "tenant",
            "installed_by",
            "length",
            "geo_length",
            "cables_routed",
            "installation_date",
            "commissioned_date",
            "comments",
            "tags",
            "created",
            "last_updated",
        ]
        brief_fields = PATHWAY_BRIEF_FIELDS


class ConduitJunctionSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_pathways-api:conduitjunction-detail",
    )
    trunk_conduit = PathwaySerializer(nested=True, required=False, allow_null=True)
    branch_conduit = PathwaySerializer(nested=True, required=False, allow_null=True)
    towards_structure = StructureSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = ConduitJunction
        fields = [
            "id",
            "url",
            "display_url",
            "display",
            "label",
            "trunk_conduit",
            "branch_conduit",
            "towards_structure",
            "position_on_trunk",
            "comments",
            "tags",
            "created",
            "last_updated",
        ]
        brief_fields = ("id", "url", "display_url", "display", "label")


class PathwayLocationSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_pathways-api:pathwaylocation-detail",
    )
    pathway = PathwaySerializer(nested=True, required=False, allow_null=True)
    site = SiteSerializer(nested=True, required=False, allow_null=True)
    location = LocationSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = PathwayLocation
        fields = [
            "id",
            "url",
            "display_url",
            "display",
            "pathway",
            "site",
            "location",
            "sequence",
            "comments",
            "tags",
            "created",
            "last_updated",
        ]
        brief_fields = ("id", "url", "display_url", "display", "pathway", "sequence")


class CableSegmentSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_pathways-api:cablesegment-detail",
    )
    cable = CableSerializer(nested=True, required=False, allow_null=True)
    pathway = PathwaySerializer(nested=True, required=False, allow_null=True)
    lashed_with = drf_serializers.PrimaryKeyRelatedField(
        many=True,
        required=False,
        queryset=CableSegment.objects.all(),
        help_text="Other cable segments lashed together with this one (symmetrical).",
    )

    class Meta:
        model = CableSegment
        fields = [
            "id",
            "url",
            "display_url",
            "display",
            "cable",
            "pathway",
            "sequence",
            "lashed_with",
            "comments",
            "tags",
            "created",
            "last_updated",
        ]
        brief_fields = ("id", "url", "display_url", "display", "cable", "pathway", "sequence")


class SiteGeometrySerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_pathways-api:sitegeometry-detail",
    )
    site = SiteSerializer(nested=True, required=False, allow_null=True)
    structure = StructureSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = SiteGeometry
        fields = [
            "id",
            "url",
            "display_url",
            "display",
            "site",
            "structure",
            "geometry",
            "comments",
            "tags",
            "created",
            "last_updated",
        ]
        brief_fields = ("id", "url", "display_url", "display", "site")


class CircuitGeometrySerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_pathways-api:circuitgeometry-detail",
    )
    circuit = CircuitSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = CircuitGeometry
        fields = [
            "id",
            "url",
            "display_url",
            "display",
            "circuit",
            "path",
            "provider_reference",
            "comments",
            "tags",
            "created",
            "last_updated",
        ]
        brief_fields = ("id", "url", "display_url", "display", "circuit")


class PlannedRouteSerializer(NetBoxModelSerializer):
    url = drf_serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_pathways-api:plannedroute-detail",
    )
    status = ChoiceField(choices=PlannedRouteStatusChoices, required=False)
    start_structure = StructureSerializer(nested=True, required=False, allow_null=True)
    end_structure = StructureSerializer(nested=True, required=False, allow_null=True)
    start_location = LocationSerializer(nested=True, required=False, allow_null=True)
    end_location = LocationSerializer(nested=True, required=False, allow_null=True)
    tenant = TenantSerializer(nested=True, required=False, allow_null=True)
    cable = CableSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = PlannedRoute
        fields = [
            "id",
            "url",
            "display_url",
            "display",
            "name",
            "status",
            "start_structure",
            "end_structure",
            "start_location",
            "end_location",
            "pathway_ids",
            "constraints",
            "tenant",
            "cable",
            "comments",
            "tags",
            "created",
            "last_updated",
        ]
        brief_fields = ("id", "url", "display_url", "display", "name", "status")

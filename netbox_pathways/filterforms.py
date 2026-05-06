"""Filter forms for list view filter UI."""

from circuits.models import Circuit, Provider
from dcim.models import Cable, Location, Site
from django import forms
from netbox.forms import NetBoxModelFilterSetForm
from tenancy.models import Tenant
from utilities.forms.fields import DynamicModelMultipleChoiceField, TagFilterField
from utilities.forms.rendering import FieldSet

from .choices import (
    AerialTypeChoices,
    BankFaceChoices,
    ConduitBankConfigChoices,
    ConduitMaterialChoices,
    EncasementTypeChoices,
    PathwayTypeChoices,
    PlannedRouteStatusChoices,
    StructureStatusChoices,
    StructureTypeChoices,
)
from .models import (
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
    PlannedRoute,
    SiteGeometry,
    Structure,
)


class StructureFilterForm(NetBoxModelFilterSetForm):
    model = Structure
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("status", "structure_type", "site_id", name="Attributes"),
        FieldSet("tenant_id", "installed_by_id", name="Tenant"),
    )
    status = forms.MultipleChoiceField(choices=StructureStatusChoices, required=False)
    structure_type = forms.MultipleChoiceField(choices=StructureTypeChoices, required=False)
    site_id = DynamicModelMultipleChoiceField(
        queryset=Site.objects.all(),
        required=False,
        label="Site",
    )
    tenant_id = DynamicModelMultipleChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        null_option="None",
        label="Tenant",
    )
    installed_by_id = DynamicModelMultipleChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        null_option="None",
        label="Installed by",
    )
    tag = TagFilterField(model)


class PathwayFilterForm(NetBoxModelFilterSetForm):
    model = Pathway
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("pathway_type", name="Attributes"),
        FieldSet("start_structure_id", "end_structure_id", "start_location_id", "end_location_id", name="Endpoints"),
        FieldSet("tenant_id", "installed_by_id", name="Tenant"),
    )
    pathway_type = forms.MultipleChoiceField(choices=PathwayTypeChoices, required=False)
    start_structure_id = DynamicModelMultipleChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        label="Start Structure",
    )
    end_structure_id = DynamicModelMultipleChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        label="End Structure",
    )
    start_location_id = DynamicModelMultipleChoiceField(
        queryset=Location.objects.all(),
        required=False,
        label="Start Location",
    )
    end_location_id = DynamicModelMultipleChoiceField(
        queryset=Location.objects.all(),
        required=False,
        label="End Location",
    )
    tenant_id = DynamicModelMultipleChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        null_option="None",
        label="Tenant",
    )
    installed_by_id = DynamicModelMultipleChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        null_option="None",
        label="Installed by",
    )
    tag = TagFilterField(model)


class ConduitFilterForm(NetBoxModelFilterSetForm):
    model = Conduit
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("material", "conduit_bank_id", name="Attributes"),
        FieldSet("start_structure_id", "end_structure_id", "start_location_id", "end_location_id", name="Endpoints"),
    )
    material = forms.MultipleChoiceField(choices=ConduitMaterialChoices, required=False)
    conduit_bank_id = DynamicModelMultipleChoiceField(
        queryset=ConduitBank.objects.all(),
        required=False,
        label="Conduit Bank",
    )
    start_structure_id = DynamicModelMultipleChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        label="Start Structure",
    )
    end_structure_id = DynamicModelMultipleChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        label="End Structure",
    )
    start_location_id = DynamicModelMultipleChoiceField(
        queryset=Location.objects.all(),
        required=False,
        label="Start Location",
    )
    end_location_id = DynamicModelMultipleChoiceField(
        queryset=Location.objects.all(),
        required=False,
        label="End Location",
    )
    tag = TagFilterField(model)


class AerialSpanFilterForm(NetBoxModelFilterSetForm):
    model = AerialSpan
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("aerial_type", name="Attributes"),
        FieldSet("start_structure_id", "end_structure_id", "start_location_id", "end_location_id", name="Endpoints"),
    )
    aerial_type = forms.MultipleChoiceField(choices=AerialTypeChoices, required=False)
    start_structure_id = DynamicModelMultipleChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        label="Start Structure",
    )
    end_structure_id = DynamicModelMultipleChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        label="End Structure",
    )
    start_location_id = DynamicModelMultipleChoiceField(
        queryset=Location.objects.all(),
        required=False,
        label="Start Location",
    )
    end_location_id = DynamicModelMultipleChoiceField(
        queryset=Location.objects.all(),
        required=False,
        label="End Location",
    )
    tag = TagFilterField(model)


class DirectBuriedFilterForm(NetBoxModelFilterSetForm):
    model = DirectBuried
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("start_structure_id", "end_structure_id", "start_location_id", "end_location_id", name="Endpoints"),
    )
    start_structure_id = DynamicModelMultipleChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        label="Start Structure",
    )
    end_structure_id = DynamicModelMultipleChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        label="End Structure",
    )
    start_location_id = DynamicModelMultipleChoiceField(
        queryset=Location.objects.all(),
        required=False,
        label="Start Location",
    )
    end_location_id = DynamicModelMultipleChoiceField(
        queryset=Location.objects.all(),
        required=False,
        label="End Location",
    )
    tag = TagFilterField(model)


class InnerductFilterForm(NetBoxModelFilterSetForm):
    model = Innerduct
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("parent_conduit_id", name="Attributes"),
    )
    parent_conduit_id = DynamicModelMultipleChoiceField(
        queryset=Conduit.objects.all(),
        required=False,
        label="Parent Conduit",
    )
    tag = TagFilterField(model)


class ConduitBankFilterForm(NetBoxModelFilterSetForm):
    model = ConduitBank
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("configuration", "encasement_type", "start_face", "end_face", name="Attributes"),
        FieldSet("start_structure_id", "end_structure_id", name="Endpoints"),
        FieldSet("tenant_id", "installed_by_id", name="Tenant"),
    )
    configuration = forms.MultipleChoiceField(choices=ConduitBankConfigChoices, required=False)
    encasement_type = forms.MultipleChoiceField(choices=EncasementTypeChoices, required=False)
    start_face = forms.MultipleChoiceField(choices=BankFaceChoices, required=False)
    end_face = forms.MultipleChoiceField(choices=BankFaceChoices, required=False)
    start_structure_id = DynamicModelMultipleChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        label="Start Structure",
    )
    end_structure_id = DynamicModelMultipleChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        label="End Structure",
    )
    tenant_id = DynamicModelMultipleChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        null_option="None",
        label="Tenant",
    )
    installed_by_id = DynamicModelMultipleChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        null_option="None",
        label="Installed by",
    )
    tag = TagFilterField(model)


class ConduitJunctionFilterForm(NetBoxModelFilterSetForm):
    model = ConduitJunction
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("trunk_conduit_id", "branch_conduit_id", name="Conduits"),
    )
    trunk_conduit_id = DynamicModelMultipleChoiceField(
        queryset=Conduit.objects.all(),
        required=False,
        label="Trunk Conduit",
    )
    branch_conduit_id = DynamicModelMultipleChoiceField(
        queryset=Conduit.objects.all(),
        required=False,
        label="Branch Conduit",
    )
    tag = TagFilterField(model)


class CableSegmentFilterForm(NetBoxModelFilterSetForm):
    model = CableSegment
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("cable_id", "pathway_id", name="Attributes"),
    )
    cable_id = DynamicModelMultipleChoiceField(
        queryset=Cable.objects.all(),
        required=False,
        label="Cable",
    )
    pathway_id = DynamicModelMultipleChoiceField(
        queryset=Pathway.objects.all(),
        required=False,
        label="Pathway",
    )
    tag = TagFilterField(model)


class PathwayLocationFilterForm(NetBoxModelFilterSetForm):
    model = PathwayLocation
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("pathway_id", "site_id", "location_id", name="Attributes"),
    )
    pathway_id = DynamicModelMultipleChoiceField(
        queryset=Pathway.objects.all(),
        required=False,
        label="Pathway",
    )
    site_id = DynamicModelMultipleChoiceField(
        queryset=Site.objects.all(),
        required=False,
        label="Site",
    )
    location_id = DynamicModelMultipleChoiceField(
        queryset=Location.objects.all(),
        required=False,
        label="Location",
    )
    tag = TagFilterField(model)


class SiteGeometryFilterForm(NetBoxModelFilterSetForm):
    model = SiteGeometry
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("site_id", "structure_id", name="Attributes"),
    )
    site_id = DynamicModelMultipleChoiceField(
        queryset=Site.objects.all(),
        required=False,
        label="Site",
    )
    structure_id = DynamicModelMultipleChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        label="Structure",
    )
    tag = TagFilterField(model)


class CircuitGeometryFilterForm(NetBoxModelFilterSetForm):
    model = CircuitGeometry
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("circuit_id", "provider_id", name="Attributes"),
    )
    circuit_id = DynamicModelMultipleChoiceField(
        queryset=Circuit.objects.all(),
        required=False,
        label="Circuit",
    )
    provider_id = DynamicModelMultipleChoiceField(
        queryset=Provider.objects.all(),
        required=False,
        label="Provider",
    )
    tag = TagFilterField(model)


class PlannedRouteFilterForm(NetBoxModelFilterSetForm):
    model = PlannedRoute
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("status", name="Attributes"),
        FieldSet("start_structure_id", "end_structure_id", "start_location_id", "end_location_id", name="Endpoints"),
        FieldSet("tenant_id", "cable_id", name="Assignment"),
    )
    status = forms.MultipleChoiceField(choices=PlannedRouteStatusChoices, required=False)
    start_structure_id = DynamicModelMultipleChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        label="Start Structure",
    )
    end_structure_id = DynamicModelMultipleChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        label="End Structure",
    )
    start_location_id = DynamicModelMultipleChoiceField(
        queryset=Location.objects.all(),
        required=False,
        label="Start Location",
    )
    end_location_id = DynamicModelMultipleChoiceField(
        queryset=Location.objects.all(),
        required=False,
        label="End Location",
    )
    tenant_id = DynamicModelMultipleChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        null_option="None",
        label="Tenant",
    )
    cable_id = DynamicModelMultipleChoiceField(
        queryset=Cable.objects.all(),
        required=False,
        label="Cable",
    )
    tag = TagFilterField(model)

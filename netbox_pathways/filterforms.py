"""Filter forms for list view filter UI."""

from circuits.models import Circuit, Provider
from dcim.models import Cable, Location, Site
from django import forms
from netbox.forms import NetBoxModelFilterSetForm
from tenancy.models import Tenant
from utilities.forms import BOOLEAN_WITH_BLANK_CHOICES
from utilities.forms.fields import ColorField, DynamicModelMultipleChoiceField, TagFilterField
from utilities.forms.rendering import FieldSet

from .choices import (
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
from .models import (
    CableSegment,
    CircuitGeometry,
    ConduitJunction,
    Pathway,
    PathwayLocation,
    PlannedRoute,
    SiteGeometry,
    Structure,
)
from .pathway_types import PATHWAY_TYPES


class StructureFilterForm(NetBoxModelFilterSetForm):
    model = Structure
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("status", "structure_type", "site_id", "location_id", name="Attributes"),
        FieldSet("tenant_id", "installed_by_id", name="Tenant"),
    )
    status = forms.MultipleChoiceField(choices=StructureStatusChoices, required=False)
    structure_type = forms.MultipleChoiceField(choices=StructureTypeChoices, required=False)
    site_id = DynamicModelMultipleChoiceField(
        queryset=Site.objects.all(),
        required=False,
        label="Site",
    )
    location_id = DynamicModelMultipleChoiceField(
        queryset=Location.objects.all(),
        required=False,
        null_option="None",
        query_params={"site_id": "$site_id"},
        label="Location",
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


# Type-specific filters offered in the per-type fieldsets. Measurements stay
# API-only, as they did on the per-type forms. Filters that several types
# carry (start_face, end_face, position) are left out on purpose and placed
# in a shared fieldset instead: a field in two fieldsets renders two inputs.
TYPE_FILTERS = (
    "configuration",
    "encasement_type",
    "material",
    "aerial_type",
    "messenger_size",
    "warning_tape",
    "tracer_wire",
    "armor_type",
    "size",
    "color",
)


def type_fieldsets(names):
    """One fieldset per pathway type, holding that type's fields from `names`.

    Grouping follows pathway_types.py, so a form never restates which field
    belongs to which type. A field shared by several types is shown once,
    under the first type in pathway_types.py that has it.
    """
    labels = dict(PathwayTypeChoices)
    placed = set()
    fieldsets = []
    for pathway_type, type_spec in PATHWAY_TYPES.items():
        own = [name for name in type_spec.fields if name in names and name not in placed]
        placed.update(own)
        if own:
            fieldsets.append(FieldSet(*own, name=labels[pathway_type]))
    return fieldsets


class PathwayFilterForm(NetBoxModelFilterSetForm):
    model = Pathway
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("status", "pathway_type", name="Attributes"),
        FieldSet("parent_id", "ancestor_id", "position", name="Hierarchy"),
        FieldSet(
            "start_structure_id",
            "end_structure_id",
            "start_location_id",
            "end_location_id",
            "start_face",
            "end_face",
            name="Endpoints",
        ),
        *type_fieldsets(TYPE_FILTERS),
        FieldSet("tenant_id", "installed_by_id", name="Tenant"),
    )
    status = forms.MultipleChoiceField(choices=PathwayStatusChoices, required=False)
    pathway_type = forms.MultipleChoiceField(choices=PathwayTypeChoices, required=False)
    parent_id = DynamicModelMultipleChoiceField(
        queryset=Pathway.objects.all(),
        required=False,
        null_option="None",
        label="Parent",
    )
    ancestor_id = DynamicModelMultipleChoiceField(
        queryset=Pathway.objects.all(),
        required=False,
        label="Inside (any depth)",
    )
    position = forms.CharField(required=False)
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
    start_face = forms.MultipleChoiceField(choices=BankFaceChoices, required=False)
    end_face = forms.MultipleChoiceField(choices=BankFaceChoices, required=False)
    configuration = forms.MultipleChoiceField(choices=ConduitBankConfigChoices, required=False)
    encasement_type = forms.MultipleChoiceField(choices=EncasementTypeChoices, required=False)
    material = forms.MultipleChoiceField(choices=ConduitMaterialChoices, required=False)
    aerial_type = forms.MultipleChoiceField(choices=AerialTypeChoices, required=False)
    messenger_size = forms.CharField(required=False)
    warning_tape = forms.NullBooleanField(
        required=False,
        widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES),
    )
    tracer_wire = forms.NullBooleanField(
        required=False,
        widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES),
    )
    armor_type = forms.CharField(required=False)
    size = forms.CharField(required=False)
    # The picker is the only practical way to filter on a stored hex code.
    color = ColorField(required=False)
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
        queryset=Pathway.objects.filter(pathway_type="conduit"),
        required=False,
        query_params={"pathway_type": "conduit"},
        label="Trunk Conduit",
    )
    branch_conduit_id = DynamicModelMultipleChoiceField(
        queryset=Pathway.objects.filter(pathway_type="conduit"),
        required=False,
        query_params={"pathway_type": "conduit"},
        label="Branch Conduit",
    )
    tag = TagFilterField(model)


class CableSegmentFilterForm(NetBoxModelFilterSetForm):
    model = CableSegment
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("cable_id", "pathway_id", "lashed_with_id", name="Attributes"),
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
    lashed_with_id = DynamicModelMultipleChoiceField(
        queryset=CableSegment.objects.all(),
        required=False,
        label="Lashed with segment",
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

from circuits.models import Circuit
from dcim.models import Cable, Location, Site
from django import forms
from leaflet.forms.widgets import LeafletWidget
from netbox.forms import NetBoxModelBulkEditForm, NetBoxModelForm, NetBoxModelImportForm
from tenancy.models import Tenant
from utilities.forms.fields import CSVModelChoiceField, DynamicModelChoiceField
from utilities.forms.rendering import FieldSet


class PathwaysLeafletWidget(LeafletWidget):
    """LeafletWidget with fix for edit/delete toolbar buttons staying disabled."""

    class Media:
        js = ('netbox_pathways/dist/fix-edit-controls.min.js',)


class PointPolygonWidget(PathwaysLeafletWidget):
    """LeafletWidget that allows point and polygon drawing but not polylines."""

    class Media:
        js = ('netbox_pathways/dist/point-polygon-widget.min.js',)


class PointOnlyWidget(PathwaysLeafletWidget):
    """LeafletWidget restricted to point drawing only."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('attrs', {})['geom_type'] = 'POINT'
        super().__init__(*args, **kwargs)

from .choices import (
    AerialTypeChoices,
    BankFaceChoices,
    ConduitBankConfigChoices,
    ConduitMaterialChoices,
    EncasementTypeChoices,
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
    SiteGeometry,
    SlackLoop,
    Structure,
)

# --- Structure ---

class StructureForm(NetBoxModelForm):
    site = DynamicModelChoiceField(queryset=Site.objects.all(), required=False, selector=True, quick_add=True)
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True, quick_add=True)

    fieldsets = (
        FieldSet('name', 'status', 'structure_type', 'site', 'tenant', 'installation_date', name='Structure'),
        FieldSet('height', 'width', 'length', 'depth', 'elevation', name='Dimensions'),
        FieldSet('location', name='Geometry'),
        FieldSet('access_notes', 'comments', 'tags', name='Details'),
    )

    class Meta:
        model = Structure
        fields = [
            'name', 'status', 'structure_type', 'site', 'tenant', 'location',
            'height', 'width', 'length', 'depth', 'elevation',
            'installation_date', 'access_notes', 'comments', 'tags',
        ]
        widgets = {
            'location': PointPolygonWidget(),
        }


class StructureImportForm(NetBoxModelImportForm):
    site = CSVModelChoiceField(
        queryset=Site.objects.all(), to_field_name='name', required=False, help_text='Site name',
    )
    tenant = CSVModelChoiceField(
        queryset=Tenant.objects.all(), to_field_name='name', required=False, help_text='Tenant name',
    )

    class Meta:
        model = Structure
        fields = [
            'name', 'status', 'structure_type', 'site', 'tenant',
            'height', 'width', 'length', 'depth', 'elevation',
            'installation_date', 'access_notes', 'comments',
        ]


class StructureBulkEditForm(NetBoxModelBulkEditForm):
    site = DynamicModelChoiceField(queryset=Site.objects.all(), required=False, selector=True)
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True)
    status = forms.ChoiceField(choices=StructureStatusChoices, required=False)
    structure_type = forms.ChoiceField(choices=StructureTypeChoices, required=False)

    model = Structure
    fieldsets = (
        FieldSet('status', 'site', 'structure_type', 'tenant'),
    )
    nullable_fields = ('site', 'tenant', 'access_notes')


# --- Pathway (base) ---

class PathwayForm(NetBoxModelForm):
    start_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(), required=False, selector=True, quick_add=True,
    )
    end_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(), required=False, selector=True, quick_add=True,
    )
    start_location = DynamicModelChoiceField(
        queryset=Location.objects.all(), required=False, selector=True, quick_add=True,
    )
    end_location = DynamicModelChoiceField(
        queryset=Location.objects.all(), required=False, selector=True, quick_add=True,
    )
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True, quick_add=True)

    fieldsets = (
        FieldSet('label', 'tenant', 'length', 'installation_date', name='Pathway'),
        FieldSet('start_structure', 'end_structure', 'start_location', 'end_location', name='Endpoints'),
        FieldSet('path', name='Geometry'),
        FieldSet('comments', 'tags', name='Details'),
    )

    class Meta:
        model = Pathway
        fields = [
            'label', 'path', 'start_structure', 'end_structure',
            'start_location', 'end_location', 'tenant',
            'length', 'installation_date', 'comments', 'tags',
        ]
        widgets = {
            'path': PathwaysLeafletWidget(),
        }


# --- Conduit ---

class ConduitForm(NetBoxModelForm):
    start_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(), required=False, selector=True, quick_add=True,
    )
    end_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(), required=False, selector=True, quick_add=True,
    )
    start_location = DynamicModelChoiceField(
        queryset=Location.objects.all(), required=False, selector=True, quick_add=True,
    )
    end_location = DynamicModelChoiceField(
        queryset=Location.objects.all(), required=False, selector=True, quick_add=True,
    )
    conduit_bank = DynamicModelChoiceField(
        queryset=ConduitBank.objects.all(), required=False, selector=True, quick_add=True,
    )
    start_junction = DynamicModelChoiceField(
        queryset=ConduitJunction.objects.all(), required=False, selector=True, quick_add=True,
    )
    end_junction = DynamicModelChoiceField(
        queryset=ConduitJunction.objects.all(), required=False, selector=True, quick_add=True,
    )

    fieldsets = (
        FieldSet('label', 'material', 'length', 'installation_date', name='Conduit'),
        FieldSet('start_structure', 'end_structure', 'start_location', 'end_location', name='Endpoints'),
        FieldSet('start_junction', 'end_junction', name='Junctions'),
        FieldSet('inner_diameter', 'outer_diameter', 'depth', name='Dimensions'),
        FieldSet('conduit_bank', 'bank_position', name='Conduit Bank'),
        FieldSet('path', name='Geometry'),
        FieldSet('comments', 'tags', name='Details'),
    )

    class Meta:
        model = Conduit
        fields = [
            'label', 'material', 'path', 'start_structure', 'end_structure',
            'start_location', 'end_location',
            'start_junction', 'end_junction',
            'inner_diameter', 'outer_diameter', 'depth',
            'conduit_bank', 'bank_position',
            'length', 'installation_date', 'comments', 'tags',
        ]
        widgets = {
            'path': PathwaysLeafletWidget(),
        }


class ConduitImportForm(NetBoxModelImportForm):
    start_structure = CSVModelChoiceField(
        queryset=Structure.objects.all(), to_field_name='name', required=False,
        help_text='Starting structure name',
    )
    end_structure = CSVModelChoiceField(
        queryset=Structure.objects.all(), to_field_name='name', required=False,
        help_text='Ending structure name',
    )

    class Meta:
        model = Conduit
        fields = [
            'label', 'material', 'start_structure', 'end_structure',
            'inner_diameter', 'outer_diameter', 'depth',
            'length', 'installation_date', 'comments',
        ]


class ConduitBulkEditForm(NetBoxModelBulkEditForm):
    material = forms.ChoiceField(choices=ConduitMaterialChoices, required=False)

    model = Conduit
    fieldsets = (
        FieldSet('material'),
    )
    nullable_fields = ('material',)


# --- Aerial Span ---

class AerialSpanForm(NetBoxModelForm):
    start_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(), required=False, selector=True, quick_add=True,
    )
    end_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(), required=False, selector=True, quick_add=True,
    )
    start_location = DynamicModelChoiceField(
        queryset=Location.objects.all(), required=False, selector=True, quick_add=True,
    )
    end_location = DynamicModelChoiceField(
        queryset=Location.objects.all(), required=False, selector=True, quick_add=True,
    )

    fieldsets = (
        FieldSet('label', 'aerial_type', 'length', 'installation_date', name='Aerial Span'),
        FieldSet('start_structure', 'end_structure', 'start_location', 'end_location', name='Endpoints'),
        FieldSet('attachment_height', 'sag', 'messenger_size', name='Physical'),
        FieldSet('wind_loading', 'ice_loading', name='Loading'),
        FieldSet('path', name='Geometry'),
        FieldSet('comments', 'tags', name='Details'),
    )

    class Meta:
        model = AerialSpan
        fields = [
            'label', 'aerial_type', 'path', 'start_structure', 'end_structure',
            'start_location', 'end_location',
            'attachment_height', 'sag', 'messenger_size',
            'wind_loading', 'ice_loading',
            'length', 'installation_date', 'comments', 'tags',
        ]
        widgets = {
            'path': PathwaysLeafletWidget(),
        }


class AerialSpanImportForm(NetBoxModelImportForm):
    start_structure = CSVModelChoiceField(
        queryset=Structure.objects.all(), to_field_name='name', help_text='Starting structure name',
    )
    end_structure = CSVModelChoiceField(
        queryset=Structure.objects.all(), to_field_name='name', help_text='Ending structure name',
    )

    class Meta:
        model = AerialSpan
        fields = [
            'label', 'aerial_type', 'start_structure', 'end_structure',
            'attachment_height', 'sag', 'messenger_size',
            'wind_loading', 'ice_loading',
            'length', 'installation_date', 'comments',
        ]


class AerialSpanBulkEditForm(NetBoxModelBulkEditForm):
    aerial_type = forms.ChoiceField(choices=AerialTypeChoices, required=False)
    messenger_size = forms.CharField(max_length=50, required=False)

    model = AerialSpan
    fieldsets = (
        FieldSet('aerial_type', 'messenger_size'),
    )
    nullable_fields = ('messenger_size', 'wind_loading', 'ice_loading')


# --- Direct Buried ---

class DirectBuriedForm(NetBoxModelForm):
    start_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(), required=False, selector=True, quick_add=True,
    )
    end_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(), required=False, selector=True, quick_add=True,
    )
    start_location = DynamicModelChoiceField(
        queryset=Location.objects.all(), required=False, selector=True, quick_add=True,
    )
    end_location = DynamicModelChoiceField(
        queryset=Location.objects.all(), required=False, selector=True, quick_add=True,
    )

    fieldsets = (
        FieldSet('label', 'length', 'installation_date', name='Direct Buried'),
        FieldSet('start_structure', 'end_structure', 'start_location', 'end_location', name='Endpoints'),
        FieldSet('burial_depth', 'warning_tape', 'tracer_wire', 'armor_type', name='Physical'),
        FieldSet('path', name='Geometry'),
        FieldSet('comments', 'tags', name='Details'),
    )

    class Meta:
        model = DirectBuried
        fields = [
            'label', 'path', 'start_structure', 'end_structure',
            'start_location', 'end_location',
            'burial_depth', 'warning_tape', 'tracer_wire', 'armor_type',
            'length', 'installation_date', 'comments', 'tags',
        ]
        widgets = {
            'path': PathwaysLeafletWidget(),
        }


# --- Innerduct ---

class InnerductForm(NetBoxModelForm):
    parent_conduit = DynamicModelChoiceField(
        queryset=Conduit.objects.all(), selector=True, quick_add=True,
    )
    start_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(), required=False, selector=True, quick_add=True,
        help_text="Leave blank to inherit from parent conduit",
    )
    end_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(), required=False, selector=True, quick_add=True,
        help_text="Leave blank to inherit from parent conduit",
    )
    start_location = DynamicModelChoiceField(
        queryset=Location.objects.all(), required=False, selector=True, quick_add=True,
        help_text="Leave blank to inherit from parent conduit",
    )
    end_location = DynamicModelChoiceField(
        queryset=Location.objects.all(), required=False, selector=True, quick_add=True,
        help_text="Leave blank to inherit from parent conduit",
    )

    fieldsets = (
        FieldSet('label', 'parent_conduit', 'size', 'color', 'position', name='Innerduct'),
        FieldSet('start_structure', 'end_structure', 'start_location', 'end_location', name='Endpoints'),
        FieldSet('length', 'installation_date', name='Physical'),
        FieldSet('path', name='Geometry'),
        FieldSet('comments', 'tags', name='Details'),
    )

    class Meta:
        model = Innerduct
        fields = [
            'label', 'parent_conduit', 'size', 'color', 'position',
            'path', 'start_structure', 'end_structure',
            'start_location', 'end_location',
            'length', 'installation_date', 'comments', 'tags',
        ]
        widgets = {
            'path': PathwaysLeafletWidget(),
        }


# --- Conduit Bank ---

class ConduitBankForm(NetBoxModelForm):
    start_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(), required=False, selector=True, quick_add=True,
    )
    end_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(), required=False, selector=True, quick_add=True,
    )
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True, quick_add=True)

    fieldsets = (
        FieldSet('label', 'tenant', name='Conduit Bank'),
        FieldSet('start_structure', 'start_face', 'end_structure', 'end_face', name='Endpoints'),
        FieldSet('configuration', 'total_conduits', 'encasement_type', name='Configuration'),
        FieldSet('path', 'installation_date', 'comments', 'tags', name='Details'),
    )

    class Meta:
        model = ConduitBank
        fields = [
            'label', 'tenant',
            'start_structure', 'start_face', 'end_structure', 'end_face',
            'configuration', 'total_conduits', 'encasement_type',
            'path', 'installation_date', 'comments', 'tags',
        ]
        widgets = {
            'path': PathwaysLeafletWidget(),
        }


class ConduitBankImportForm(NetBoxModelImportForm):
    start_structure = CSVModelChoiceField(
        queryset=Structure.objects.all(), to_field_name='name',
        required=False, help_text='Start structure name',
    )
    end_structure = CSVModelChoiceField(
        queryset=Structure.objects.all(), to_field_name='name',
        required=False, help_text='End structure name',
    )

    class Meta:
        model = ConduitBank
        fields = [
            'label', 'start_structure', 'start_face', 'end_structure', 'end_face',
            'configuration', 'total_conduits', 'encasement_type',
            'installation_date', 'comments',
        ]


class ConduitBankBulkEditForm(NetBoxModelBulkEditForm):
    start_face = forms.ChoiceField(choices=BankFaceChoices, required=False)
    end_face = forms.ChoiceField(choices=BankFaceChoices, required=False)
    configuration = forms.ChoiceField(choices=ConduitBankConfigChoices, required=False)
    encasement_type = forms.ChoiceField(choices=EncasementTypeChoices, required=False)

    model = ConduitBank
    fieldsets = (
        FieldSet('start_face', 'end_face'),
        FieldSet('configuration', 'encasement_type'),
    )
    nullable_fields = ('start_face', 'end_face', 'encasement_type')


# --- Conduit Junction ---

class ConduitJunctionForm(NetBoxModelForm):
    trunk_conduit = DynamicModelChoiceField(
        queryset=Conduit.objects.all(), selector=True, quick_add=True,
    )
    branch_conduit = DynamicModelChoiceField(
        queryset=Conduit.objects.all(), selector=True, quick_add=True,
    )
    towards_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(), selector=True, quick_add=True,
    )

    fieldsets = (
        FieldSet('label', name='Junction'),
        FieldSet('trunk_conduit', 'branch_conduit', 'towards_structure', 'position_on_trunk', name='Configuration'),
        FieldSet('comments', 'tags', name='Details'),
    )

    class Meta:
        model = ConduitJunction
        fields = [
            'label', 'trunk_conduit', 'branch_conduit',
            'towards_structure', 'position_on_trunk',
            'comments', 'tags',
        ]


# --- Cable Segment ---

class CableSegmentForm(NetBoxModelForm):
    cable = DynamicModelChoiceField(queryset=Cable.objects.all(), selector=True)
    pathway = DynamicModelChoiceField(
        queryset=Pathway.objects.all(), required=False, selector=True,
    )

    fieldsets = (
        FieldSet('cable', 'pathway', name='Cable Segment'),
        FieldSet('comments', 'tags', name='Details'),
    )

    class Meta:
        model = CableSegment
        fields = [
            'cable', 'pathway',
            'comments', 'tags',
        ]


class CableSegmentImportForm(NetBoxModelImportForm):
    class Meta:
        model = CableSegment
        fields = [
            'cable', 'pathway', 'comments',
        ]


# --- Slack Loop ---

class SlackLoopForm(NetBoxModelForm):
    cable = DynamicModelChoiceField(queryset=Cable.objects.all(), selector=True)
    structure = DynamicModelChoiceField(queryset=Structure.objects.all(), selector=True)
    pathway = DynamicModelChoiceField(
        queryset=Pathway.objects.all(), required=False, selector=True,
    )

    fieldsets = (
        FieldSet('cable', 'structure', 'pathway', 'length', name='Slack Loop'),
        FieldSet('comments', 'tags', name='Details'),
    )

    class Meta:
        model = SlackLoop
        fields = ['cable', 'structure', 'pathway', 'length', 'comments', 'tags']


# --- Pathway Location ---

class PathwayLocationForm(NetBoxModelForm):
    pathway = DynamicModelChoiceField(
        queryset=Pathway.objects.all(), selector=True,
    )
    site = DynamicModelChoiceField(
        queryset=Site.objects.all(), required=False, selector=True, quick_add=True,
    )
    location = DynamicModelChoiceField(
        queryset=Location.objects.all(), required=False, selector=True, quick_add=True,
    )

    fieldsets = (
        FieldSet('pathway', 'site', 'location', 'sequence', name='Waypoint'),
        FieldSet('comments', 'tags', name='Details'),
    )

    class Meta:
        model = PathwayLocation
        fields = [
            'pathway', 'site', 'location', 'sequence', 'comments', 'tags',
        ]


# --- Site Geometry ---

class SiteGeometryForm(NetBoxModelForm):
    site = DynamicModelChoiceField(
        queryset=Site.objects.all(), selector=True, quick_add=True,
    )
    structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(), required=False, selector=True, quick_add=True,
    )

    fieldsets = (
        FieldSet('site', 'structure', name='Site Geometry'),
        FieldSet('geometry', name='Geometry'),
        FieldSet('comments', 'tags', name='Details'),
    )

    class Meta:
        model = SiteGeometry
        fields = ['site', 'structure', 'geometry', 'comments', 'tags']
        widgets = {
            'geometry': PointPolygonWidget(),
        }


# --- Circuit Geometry ---

class CircuitGeometryForm(NetBoxModelForm):
    circuit = DynamicModelChoiceField(
        queryset=Circuit.objects.all(), selector=True,
    )

    fieldsets = (
        FieldSet('circuit', 'provider_reference', name='Circuit Route'),
        FieldSet('path', name='Route Geometry'),
        FieldSet('comments', 'tags', name='Details'),
    )

    class Meta:
        model = CircuitGeometry
        fields = ['circuit', 'path', 'provider_reference', 'comments', 'tags']
        widgets = {
            'path': PathwaysLeafletWidget(),
        }

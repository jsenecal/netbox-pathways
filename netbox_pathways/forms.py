from dcim.models import Cable, Location, Site
from django import forms
from netbox.forms import NetBoxModelBulkEditForm, NetBoxModelForm, NetBoxModelImportForm
from utilities.forms.fields import CSVModelChoiceField, DynamicModelChoiceField

from .models import (
    AerialSpan,
    CableSegment,
    Conduit,
    ConduitBank,
    ConduitJunction,
    DirectBuried,
    Innerduct,
    Pathway,
    PathwayLocation,
    Structure,
)

# --- Structure ---

class StructureForm(NetBoxModelForm):
    site = DynamicModelChoiceField(queryset=Site.objects.all())

    class Meta:
        model = Structure
        fields = [
            'name', 'structure_type', 'site', 'location', 'elevation',
            'installation_date', 'owner', 'access_notes', 'comments', 'tags',
        ]
        widgets = {
            'location': forms.HiddenInput(),
        }


class StructureImportForm(NetBoxModelImportForm):
    site = CSVModelChoiceField(queryset=Site.objects.all(), to_field_name='name', help_text='Site name')

    class Meta:
        model = Structure
        fields = [
            'name', 'structure_type', 'site', 'elevation',
            'installation_date', 'owner', 'access_notes', 'comments',
        ]


class StructureBulkEditForm(NetBoxModelBulkEditForm):
    site = DynamicModelChoiceField(queryset=Site.objects.all(), required=False)
    structure_type = forms.ChoiceField(choices=[], required=False)
    owner = forms.CharField(max_length=100, required=False)

    model = Structure
    fieldsets = (
        (None, ('site', 'structure_type', 'owner')),
    )
    nullable_fields = ('owner', 'access_notes')


# --- Pathway (base) ---

class PathwayForm(NetBoxModelForm):
    start_structure = DynamicModelChoiceField(queryset=Structure.objects.all(), required=False)
    end_structure = DynamicModelChoiceField(queryset=Structure.objects.all(), required=False)
    start_location = DynamicModelChoiceField(queryset=Location.objects.all(), required=False)
    end_location = DynamicModelChoiceField(queryset=Location.objects.all(), required=False)

    class Meta:
        model = Pathway
        fields = [
            'name', 'path', 'start_structure', 'end_structure',
            'start_location', 'end_location',
            'length', 'cable_count', 'max_cable_count',
            'installation_date', 'comments', 'tags',
        ]
        widgets = {
            'path': forms.HiddenInput(),
        }


# --- Conduit ---

class ConduitForm(NetBoxModelForm):
    start_structure = DynamicModelChoiceField(queryset=Structure.objects.all(), required=False)
    end_structure = DynamicModelChoiceField(queryset=Structure.objects.all(), required=False)
    start_location = DynamicModelChoiceField(queryset=Location.objects.all(), required=False)
    end_location = DynamicModelChoiceField(queryset=Location.objects.all(), required=False)
    conduit_bank = DynamicModelChoiceField(queryset=ConduitBank.objects.all(), required=False)
    start_junction = DynamicModelChoiceField(queryset=ConduitJunction.objects.all(), required=False)
    end_junction = DynamicModelChoiceField(queryset=ConduitJunction.objects.all(), required=False)

    class Meta:
        model = Conduit
        fields = [
            'name', 'material', 'path', 'start_structure', 'end_structure',
            'start_location', 'end_location',
            'start_junction', 'end_junction',
            'inner_diameter', 'outer_diameter', 'depth',
            'conduit_bank', 'bank_position',
            'length', 'cable_count', 'max_cable_count',
            'installation_date', 'comments', 'tags',
        ]
        widgets = {
            'path': forms.HiddenInput(),
        }


class ConduitImportForm(NetBoxModelImportForm):
    start_structure = CSVModelChoiceField(
        queryset=Structure.objects.all(), to_field_name='name', help_text='Starting structure name',
    )
    end_structure = CSVModelChoiceField(
        queryset=Structure.objects.all(), to_field_name='name', help_text='Ending structure name',
    )

    class Meta:
        model = Conduit
        fields = [
            'name', 'material', 'start_structure', 'end_structure',
            'inner_diameter', 'outer_diameter', 'depth',
            'length', 'cable_count', 'max_cable_count',
            'installation_date', 'comments',
        ]


class ConduitBulkEditForm(NetBoxModelBulkEditForm):
    material = forms.ChoiceField(choices=[], required=False)
    max_cable_count = forms.IntegerField(required=False, min_value=1)

    model = Conduit
    fieldsets = (
        (None, ('material', 'max_cable_count')),
    )
    nullable_fields = ('material',)


# --- Aerial Span ---

class AerialSpanForm(NetBoxModelForm):
    start_structure = DynamicModelChoiceField(queryset=Structure.objects.all(), required=False)
    end_structure = DynamicModelChoiceField(queryset=Structure.objects.all(), required=False)
    start_location = DynamicModelChoiceField(queryset=Location.objects.all(), required=False)
    end_location = DynamicModelChoiceField(queryset=Location.objects.all(), required=False)

    class Meta:
        model = AerialSpan
        fields = [
            'name', 'aerial_type', 'path', 'start_structure', 'end_structure',
            'start_location', 'end_location',
            'attachment_height', 'sag', 'messenger_size',
            'wind_loading', 'ice_loading',
            'length', 'cable_count', 'max_cable_count',
            'installation_date', 'comments', 'tags',
        ]
        widgets = {
            'path': forms.HiddenInput(),
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
            'name', 'aerial_type', 'start_structure', 'end_structure',
            'attachment_height', 'sag', 'messenger_size',
            'wind_loading', 'ice_loading',
            'length', 'cable_count', 'max_cable_count',
            'installation_date', 'comments',
        ]


class AerialSpanBulkEditForm(NetBoxModelBulkEditForm):
    aerial_type = forms.ChoiceField(choices=[], required=False)
    max_cable_count = forms.IntegerField(required=False, min_value=1)
    messenger_size = forms.CharField(max_length=50, required=False)

    model = AerialSpan
    fieldsets = (
        (None, ('aerial_type', 'max_cable_count', 'messenger_size')),
    )
    nullable_fields = ('messenger_size', 'wind_loading', 'ice_loading')


# --- Direct Buried ---

class DirectBuriedForm(NetBoxModelForm):
    start_structure = DynamicModelChoiceField(queryset=Structure.objects.all(), required=False)
    end_structure = DynamicModelChoiceField(queryset=Structure.objects.all(), required=False)
    start_location = DynamicModelChoiceField(queryset=Location.objects.all(), required=False)
    end_location = DynamicModelChoiceField(queryset=Location.objects.all(), required=False)

    class Meta:
        model = DirectBuried
        fields = [
            'name', 'path', 'start_structure', 'end_structure',
            'start_location', 'end_location',
            'burial_depth', 'warning_tape', 'tracer_wire', 'armor_type',
            'length', 'cable_count', 'max_cable_count',
            'installation_date', 'comments', 'tags',
        ]
        widgets = {
            'path': forms.HiddenInput(),
        }


# --- Innerduct ---

class InnerductForm(NetBoxModelForm):
    parent_conduit = DynamicModelChoiceField(queryset=Conduit.objects.all())
    start_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(), required=False,
        help_text="Leave blank to inherit from parent conduit",
    )
    end_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(), required=False,
        help_text="Leave blank to inherit from parent conduit",
    )
    start_location = DynamicModelChoiceField(
        queryset=Location.objects.all(), required=False,
        help_text="Leave blank to inherit from parent conduit",
    )
    end_location = DynamicModelChoiceField(
        queryset=Location.objects.all(), required=False,
        help_text="Leave blank to inherit from parent conduit",
    )

    class Meta:
        model = Innerduct
        fields = [
            'name', 'parent_conduit', 'size', 'color', 'position',
            'path', 'start_structure', 'end_structure',
            'start_location', 'end_location',
            'length', 'cable_count', 'max_cable_count',
            'installation_date', 'comments', 'tags',
        ]
        widgets = {
            'path': forms.HiddenInput(),
        }


# --- Conduit Bank ---

class ConduitBankForm(NetBoxModelForm):
    structure = DynamicModelChoiceField(queryset=Structure.objects.all())

    class Meta:
        model = ConduitBank
        fields = [
            'name', 'structure',
            'configuration', 'total_conduits', 'encasement_type',
            'installation_date', 'comments', 'tags',
        ]


class ConduitBankImportForm(NetBoxModelImportForm):
    structure = CSVModelChoiceField(
        queryset=Structure.objects.all(), to_field_name='name', help_text='Structure name',
    )

    class Meta:
        model = ConduitBank
        fields = [
            'name', 'structure',
            'configuration', 'total_conduits', 'encasement_type',
            'installation_date', 'comments',
        ]


class ConduitBankBulkEditForm(NetBoxModelBulkEditForm):
    configuration = forms.ChoiceField(choices=[], required=False)
    encasement_type = forms.ChoiceField(choices=[], required=False)

    model = ConduitBank
    fieldsets = (
        (None, ('configuration', 'encasement_type')),
    )
    nullable_fields = ('encasement_type',)


# --- Conduit Junction ---

class ConduitJunctionForm(NetBoxModelForm):
    trunk_conduit = DynamicModelChoiceField(queryset=Conduit.objects.all())
    branch_conduit = DynamicModelChoiceField(queryset=Conduit.objects.all())
    towards_structure = DynamicModelChoiceField(queryset=Structure.objects.all())

    class Meta:
        model = ConduitJunction
        fields = [
            'name', 'trunk_conduit', 'branch_conduit',
            'towards_structure', 'position_on_trunk',
            'comments', 'tags',
        ]


# --- Cable Segment ---

class CableSegmentForm(NetBoxModelForm):
    cable = DynamicModelChoiceField(queryset=Cable.objects.all())
    pathway = DynamicModelChoiceField(queryset=Pathway.objects.all(), required=False)

    class Meta:
        model = CableSegment
        fields = [
            'cable', 'pathway', 'sequence',
            'enter_point', 'exit_point',
            'slack_loop_location', 'slack_length',
            'comments', 'tags',
        ]
        widgets = {
            'enter_point': forms.HiddenInput(),
            'exit_point': forms.HiddenInput(),
            'slack_loop_location': forms.HiddenInput(),
        }


class CableSegmentImportForm(NetBoxModelImportForm):
    class Meta:
        model = CableSegment
        fields = [
            'cable', 'pathway', 'sequence', 'slack_length', 'comments',
        ]


# --- Pathway Location ---

class PathwayLocationForm(NetBoxModelForm):
    pathway = DynamicModelChoiceField(queryset=Pathway.objects.all())
    site = DynamicModelChoiceField(queryset=Site.objects.all(), required=False)
    location = DynamicModelChoiceField(queryset=Location.objects.all(), required=False)

    class Meta:
        model = PathwayLocation
        fields = [
            'pathway', 'site', 'location', 'sequence', 'comments', 'tags',
        ]

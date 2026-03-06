from django import forms
from django.contrib.gis.forms import PointField, LineStringField
from netbox.forms import NetBoxModelForm, NetBoxModelImportForm, NetBoxModelBulkEditForm
from utilities.forms.fields import DynamicModelChoiceField, CSVModelChoiceField
from dcim.models import Site
from .models import (
    FiberStructure, FiberPathway, FiberConduit, FiberAerialSpan,
    FiberDirectBuried, FiberInnerduct, FiberSplice, FiberCableSegment
)


class FiberStructureForm(NetBoxModelForm):
    site = DynamicModelChoiceField(
        queryset=Site.objects.all(),
        required=True
    )
    
    class Meta:
        model = FiberStructure
        fields = [
            'name', 'structure_type', 'site', 'location', 'elevation',
            'installation_date', 'owner', 'access_notes', 'comments', 'tags',
        ]
        widgets = {
            'location': forms.HiddenInput(),  # Will be handled by map widget
        }


class FiberStructureImportForm(NetBoxModelImportForm):
    site = CSVModelChoiceField(
        queryset=Site.objects.all(),
        to_field_name='name',
        help_text='Site name'
    )
    
    class Meta:
        model = FiberStructure
        fields = [
            'name', 'structure_type', 'site', 'elevation',
            'installation_date', 'owner', 'access_notes', 'comments',
        ]


class FiberStructureBulkEditForm(NetBoxModelBulkEditForm):
    site = DynamicModelChoiceField(
        queryset=Site.objects.all(),
        required=False
    )
    structure_type = forms.ChoiceField(
        choices=[],
        required=False
    )
    owner = forms.CharField(
        max_length=100,
        required=False
    )
    
    model = FiberStructure
    fieldsets = (
        (None, ('site', 'structure_type', 'owner')),
    )
    nullable_fields = ('owner', 'access_notes')


# Base Pathway Form
class FiberPathwayForm(NetBoxModelForm):
    start_structure = DynamicModelChoiceField(
        queryset=FiberStructure.objects.all(),
        required=True
    )
    end_structure = DynamicModelChoiceField(
        queryset=FiberStructure.objects.all(),
        required=True
    )
    
    class Meta:
        model = FiberPathway
        fields = [
            'name', 'path', 'start_structure', 'end_structure',
            'length', 'cable_count', 'max_cable_count', 
            'installation_date', 'comments', 'tags',
        ]
        widgets = {
            'path': forms.HiddenInput(),  # Will be handled by map widget
        }


# Conduit Forms
class FiberConduitForm(NetBoxModelForm):
    start_structure = DynamicModelChoiceField(
        queryset=FiberStructure.objects.all(),
        required=True
    )
    end_structure = DynamicModelChoiceField(
        queryset=FiberStructure.objects.all(),
        required=True
    )
    
    class Meta:
        model = FiberConduit
        fields = [
            'name', 'material', 'path', 'start_structure', 'end_structure',
            'inner_diameter', 'outer_diameter', 'depth', 'duct_count',
            'length', 'cable_count', 'max_cable_count', 
            'installation_date', 'comments', 'tags',
        ]
        widgets = {
            'path': forms.HiddenInput(),  # Will be handled by map widget
        }


class FiberConduitImportForm(NetBoxModelImportForm):
    start_structure = CSVModelChoiceField(
        queryset=FiberStructure.objects.all(),
        to_field_name='name',
        help_text='Starting structure name'
    )
    end_structure = CSVModelChoiceField(
        queryset=FiberStructure.objects.all(),
        to_field_name='name',
        help_text='Ending structure name'
    )
    
    class Meta:
        model = FiberConduit
        fields = [
            'name', 'material', 'start_structure', 'end_structure',
            'inner_diameter', 'outer_diameter', 'depth', 'duct_count',
            'length', 'cable_count', 'max_cable_count', 
            'installation_date', 'comments',
        ]


class FiberConduitBulkEditForm(NetBoxModelBulkEditForm):
    material = forms.ChoiceField(
        choices=[],
        required=False
    )
    max_cable_count = forms.IntegerField(
        required=False,
        min_value=1
    )
    duct_count = forms.IntegerField(
        required=False,
        min_value=1
    )
    
    model = FiberConduit
    fieldsets = (
        (None, ('material', 'max_cable_count', 'duct_count')),
    )
    nullable_fields = ('material',)


# Aerial Span Forms
class FiberAerialSpanForm(NetBoxModelForm):
    start_structure = DynamicModelChoiceField(
        queryset=FiberStructure.objects.all(),
        required=True
    )
    end_structure = DynamicModelChoiceField(
        queryset=FiberStructure.objects.all(),
        required=True
    )
    
    class Meta:
        model = FiberAerialSpan
        fields = [
            'name', 'aerial_type', 'path', 'start_structure', 'end_structure',
            'attachment_height', 'sag', 'messenger_size', 
            'wind_loading', 'ice_loading',
            'length', 'cable_count', 'max_cable_count', 
            'installation_date', 'comments', 'tags',
        ]
        widgets = {
            'path': forms.HiddenInput(),  # Will be handled by map widget
        }


class FiberAerialSpanImportForm(NetBoxModelImportForm):
    start_structure = CSVModelChoiceField(
        queryset=FiberStructure.objects.all(),
        to_field_name='name',
        help_text='Starting structure name'
    )
    end_structure = CSVModelChoiceField(
        queryset=FiberStructure.objects.all(),
        to_field_name='name',
        help_text='Ending structure name'
    )
    
    class Meta:
        model = FiberAerialSpan
        fields = [
            'name', 'aerial_type', 'start_structure', 'end_structure',
            'attachment_height', 'sag', 'messenger_size',
            'wind_loading', 'ice_loading',
            'length', 'cable_count', 'max_cable_count', 
            'installation_date', 'comments',
        ]


class FiberAerialSpanBulkEditForm(NetBoxModelBulkEditForm):
    aerial_type = forms.ChoiceField(
        choices=[],
        required=False
    )
    max_cable_count = forms.IntegerField(
        required=False,
        min_value=1
    )
    messenger_size = forms.CharField(
        max_length=50,
        required=False
    )
    
    model = FiberAerialSpan
    fieldsets = (
        (None, ('aerial_type', 'max_cable_count', 'messenger_size')),
    )
    nullable_fields = ('messenger_size', 'wind_loading', 'ice_loading')


# Direct Buried Forms
class FiberDirectBuriedForm(NetBoxModelForm):
    start_structure = DynamicModelChoiceField(
        queryset=FiberStructure.objects.all(),
        required=True
    )
    end_structure = DynamicModelChoiceField(
        queryset=FiberStructure.objects.all(),
        required=True
    )
    
    class Meta:
        model = FiberDirectBuried
        fields = [
            'name', 'path', 'start_structure', 'end_structure',
            'burial_depth', 'warning_tape', 'tracer_wire', 'armor_type',
            'length', 'cable_count', 'max_cable_count', 
            'installation_date', 'comments', 'tags',
        ]
        widgets = {
            'path': forms.HiddenInput(),  # Will be handled by map widget
        }


# Innerduct Forms
class FiberInnerductForm(NetBoxModelForm):
    parent_conduit = DynamicModelChoiceField(
        queryset=FiberConduit.objects.all(),
        required=True
    )
    start_structure = DynamicModelChoiceField(
        queryset=FiberStructure.objects.all(),
        required=False,
        help_text="Leave blank to inherit from parent conduit"
    )
    end_structure = DynamicModelChoiceField(
        queryset=FiberStructure.objects.all(),
        required=False,
        help_text="Leave blank to inherit from parent conduit"
    )
    
    class Meta:
        model = FiberInnerduct
        fields = [
            'name', 'parent_conduit', 'size', 'color', 'position',
            'path', 'start_structure', 'end_structure',
            'length', 'cable_count', 'max_cable_count', 
            'installation_date', 'comments', 'tags',
        ]
        widgets = {
            'path': forms.HiddenInput(),  # Will be handled by map widget
        }
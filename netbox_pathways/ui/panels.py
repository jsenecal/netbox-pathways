from django.utils.translation import gettext_lazy as _
from netbox.ui import attrs
from netbox.ui.panels import ObjectAttributesPanel


class StructurePanel(ObjectAttributesPanel):
    name = attrs.TextAttr('name', label=_('Name'))
    structure_type = attrs.ChoiceAttr('structure_type', label=_('Type'))
    site = attrs.RelatedObjectAttr('site', linkify=True, label=_('Site'))
    elevation = attrs.NumericAttr('elevation', label=_('Elevation'))
    owner = attrs.TextAttr('owner', label=_('Owner'))
    installation_date = attrs.TextAttr('installation_date', label=_('Installation date'))
    access_notes = attrs.TextAttr('access_notes', label=_('Access notes'))


class PathwayPanel(ObjectAttributesPanel):
    name = attrs.TextAttr('name', label=_('Name'))
    pathway_type = attrs.ChoiceAttr('pathway_type', label=_('Type'))
    start_structure = attrs.RelatedObjectAttr('start_structure', linkify=True, label=_('Start structure'))
    end_structure = attrs.RelatedObjectAttr('end_structure', linkify=True, label=_('End structure'))
    start_location = attrs.RelatedObjectAttr('start_location', linkify=True, label=_('Start location'))
    end_location = attrs.RelatedObjectAttr('end_location', linkify=True, label=_('End location'))
    length = attrs.NumericAttr('length', label=_('Length (m)'))
    cable_count = attrs.NumericAttr('cable_count', label=_('Cable count'))
    max_cable_count = attrs.NumericAttr('max_cable_count', label=_('Max cables'))
    installation_date = attrs.TextAttr('installation_date', label=_('Installation date'))


class ConduitPanel(ObjectAttributesPanel):
    name = attrs.TextAttr('name', label=_('Name'))
    material = attrs.ChoiceAttr('material', label=_('Material'))
    start_structure = attrs.RelatedObjectAttr('start_structure', linkify=True, label=_('Start structure'))
    end_structure = attrs.RelatedObjectAttr('end_structure', linkify=True, label=_('End structure'))
    start_location = attrs.RelatedObjectAttr('start_location', linkify=True, label=_('Start location'))
    end_location = attrs.RelatedObjectAttr('end_location', linkify=True, label=_('End location'))
    conduit_bank = attrs.RelatedObjectAttr('conduit_bank', linkify=True, label=_('Conduit bank'))
    bank_position = attrs.TextAttr('bank_position', label=_('Bank position'))
    inner_diameter = attrs.NumericAttr('inner_diameter', label=_('Inner diameter (mm)'))
    outer_diameter = attrs.NumericAttr('outer_diameter', label=_('Outer diameter (mm)'))
    depth = attrs.NumericAttr('depth', label=_('Depth (m)'))
    length = attrs.NumericAttr('length', label=_('Length (m)'))
    cable_count = attrs.NumericAttr('cable_count', label=_('Cable count'))
    max_cable_count = attrs.NumericAttr('max_cable_count', label=_('Max cables'))
    installation_date = attrs.TextAttr('installation_date', label=_('Installation date'))


class AerialSpanPanel(ObjectAttributesPanel):
    name = attrs.TextAttr('name', label=_('Name'))
    aerial_type = attrs.ChoiceAttr('aerial_type', label=_('Aerial type'))
    start_structure = attrs.RelatedObjectAttr('start_structure', linkify=True, label=_('Start structure'))
    end_structure = attrs.RelatedObjectAttr('end_structure', linkify=True, label=_('End structure'))
    start_location = attrs.RelatedObjectAttr('start_location', linkify=True, label=_('Start location'))
    end_location = attrs.RelatedObjectAttr('end_location', linkify=True, label=_('End location'))
    attachment_height = attrs.NumericAttr('attachment_height', label=_('Attachment height (m)'))
    sag = attrs.NumericAttr('sag', label=_('Sag (m)'))
    messenger_size = attrs.TextAttr('messenger_size', label=_('Messenger size'))
    wind_loading = attrs.TextAttr('wind_loading', label=_('Wind loading'))
    ice_loading = attrs.TextAttr('ice_loading', label=_('Ice loading'))
    length = attrs.NumericAttr('length', label=_('Length (m)'))
    cable_count = attrs.NumericAttr('cable_count', label=_('Cable count'))
    max_cable_count = attrs.NumericAttr('max_cable_count', label=_('Max cables'))
    installation_date = attrs.TextAttr('installation_date', label=_('Installation date'))


class DirectBuriedPanel(ObjectAttributesPanel):
    name = attrs.TextAttr('name', label=_('Name'))
    start_structure = attrs.RelatedObjectAttr('start_structure', linkify=True, label=_('Start structure'))
    end_structure = attrs.RelatedObjectAttr('end_structure', linkify=True, label=_('End structure'))
    start_location = attrs.RelatedObjectAttr('start_location', linkify=True, label=_('Start location'))
    end_location = attrs.RelatedObjectAttr('end_location', linkify=True, label=_('End location'))
    burial_depth = attrs.NumericAttr('burial_depth', label=_('Burial depth (m)'))
    warning_tape = attrs.BooleanAttr('warning_tape', label=_('Warning tape'))
    tracer_wire = attrs.BooleanAttr('tracer_wire', label=_('Tracer wire'))
    armor_type = attrs.TextAttr('armor_type', label=_('Armor type'))
    length = attrs.NumericAttr('length', label=_('Length (m)'))
    cable_count = attrs.NumericAttr('cable_count', label=_('Cable count'))
    max_cable_count = attrs.NumericAttr('max_cable_count', label=_('Max cables'))
    installation_date = attrs.TextAttr('installation_date', label=_('Installation date'))


class InnerductPanel(ObjectAttributesPanel):
    name = attrs.TextAttr('name', label=_('Name'))
    parent_conduit = attrs.RelatedObjectAttr('parent_conduit', linkify=True, label=_('Parent conduit'))
    size = attrs.TextAttr('size', label=_('Size'))
    color = attrs.TextAttr('color', label=_('Color'))
    position = attrs.TextAttr('position', label=_('Position'))
    length = attrs.NumericAttr('length', label=_('Length (m)'))
    cable_count = attrs.NumericAttr('cable_count', label=_('Cable count'))
    max_cable_count = attrs.NumericAttr('max_cable_count', label=_('Max cables'))
    installation_date = attrs.TextAttr('installation_date', label=_('Installation date'))


class ConduitBankPanel(ObjectAttributesPanel):
    name = attrs.TextAttr('name', label=_('Name'))
    structure = attrs.RelatedObjectAttr('structure', linkify=True, label=_('Structure'))
    configuration = attrs.ChoiceAttr('configuration', label=_('Configuration'))
    total_conduits = attrs.NumericAttr('total_conduits', label=_('Total conduit positions'))
    encasement_type = attrs.ChoiceAttr('encasement_type', label=_('Encasement type'))
    installation_date = attrs.TextAttr('installation_date', label=_('Installation date'))


class ConduitJunctionPanel(ObjectAttributesPanel):
    name = attrs.TextAttr('name', label=_('Name'))
    trunk_conduit = attrs.RelatedObjectAttr('trunk_conduit', linkify=True, label=_('Trunk conduit'))
    branch_conduit = attrs.RelatedObjectAttr('branch_conduit', linkify=True, label=_('Branch conduit'))
    towards_structure = attrs.RelatedObjectAttr('towards_structure', linkify=True, label=_('Towards structure'))
    position_on_trunk = attrs.NumericAttr('position_on_trunk', label=_('Position on trunk'))


class PathwayLocationPanel(ObjectAttributesPanel):
    pathway = attrs.RelatedObjectAttr('pathway', linkify=True, label=_('Pathway'))
    site = attrs.RelatedObjectAttr('site', linkify=True, label=_('Site'))
    location = attrs.RelatedObjectAttr('location', linkify=True, label=_('Location'))
    sequence = attrs.NumericAttr('sequence', label=_('Sequence'))


class CableSegmentPanel(ObjectAttributesPanel):
    cable = attrs.RelatedObjectAttr('cable', linkify=True, label=_('Cable'))
    pathway = attrs.RelatedObjectAttr('pathway', linkify=True, label=_('Pathway'))
    sequence = attrs.NumericAttr('sequence', label=_('Sequence'))
    slack_length = attrs.NumericAttr('slack_length', label=_('Slack length (m)'))

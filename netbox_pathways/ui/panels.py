from django.utils.translation import gettext_lazy as _
from netbox.ui import attrs
from netbox.ui.panels import ObjectAttributesPanel, ObjectsTablePanel

from ..choices import PathwayTypeChoices
from ..pathway_types import PATHWAY_TYPES


class HideIfEmptyObjectsTablePanel(ObjectsTablePanel):
    """ObjectsTablePanel that hides itself when no rows would render.

    The base panel renders an HTMX-loaded table that is empty when the
    filtered queryset has no rows. For relationships with a physical cap on
    cardinality (where most instances will have zero peers), this avoids a
    permanent empty table on every detail page.

    The `empty_check` kwarg is a callable taking the template context and
    returning True if the panel should be rendered.
    """

    def __init__(self, *args, empty_check=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._empty_check = empty_check

    def should_render(self, context):
        if not super().should_render(context):
            return False
        if self._empty_check is None:
            return True
        return self._empty_check(context)


class StructurePanel(ObjectAttributesPanel):
    name = attrs.TextAttr("name", label=_("Name"))
    status = attrs.ChoiceAttr("status", label=_("Status"))
    structure_type = attrs.ChoiceAttr("structure_type", label=_("Type"))
    site = attrs.RelatedObjectAttr("site", linkify=True, label=_("Site"))
    location = attrs.RelatedObjectAttr("location", linkify=True, label=_("Location"))
    tenant = attrs.RelatedObjectAttr("tenant", linkify=True, label=_("Tenant"))
    installed_by = attrs.RelatedObjectAttr("installed_by", linkify=True, label=_("Installed by"))
    height = attrs.NumericAttr("height", label=_("Height (m)"))
    width = attrs.NumericAttr("width", label=_("Width (m)"))
    length = attrs.NumericAttr("length", label=_("Length (m)"))
    depth = attrs.NumericAttr("depth", label=_("Depth (m)"))
    elevation = attrs.NumericAttr("elevation", label=_("Elevation (m)"))
    installation_date = attrs.TextAttr("installation_date", label=_("Installation date"))
    commissioned_date = attrs.TextAttr("commissioned_date", label=_("Commissioned date"))
    access_notes = attrs.TextAttr("access_notes", label=_("Access notes"))


class PathwayPanel(ObjectAttributesPanel):
    """The attributes every pathway has, whatever its type."""

    label = attrs.TextAttr("label", label=_("Label"))
    status = attrs.ChoiceAttr("status", label=_("Status"))
    pathway_type = attrs.ChoiceAttr("pathway_type", label=_("Type"))
    parent = attrs.NestedObjectAttr("parent", linkify=True, label=_("Parent"))
    start_structure = attrs.RelatedObjectAttr("start_structure", linkify=True, label=_("Start structure"))
    end_structure = attrs.RelatedObjectAttr("end_structure", linkify=True, label=_("End structure"))
    start_location = attrs.RelatedObjectAttr("start_location", linkify=True, label=_("Start location"))
    end_location = attrs.RelatedObjectAttr("end_location", linkify=True, label=_("End location"))
    tenant = attrs.RelatedObjectAttr("tenant", linkify=True, label=_("Tenant"))
    installed_by = attrs.RelatedObjectAttr("installed_by", linkify=True, label=_("Installed by"))
    length = attrs.NumericAttr("length", label=_("Length (m, as-built)"))
    geo_length = attrs.NumericAttr("geo_length", label=_("Geo length (m, drawn)"))

    installation_date = attrs.TextAttr("installation_date", label=_("Installation date"))
    commissioned_date = attrs.TextAttr("commissioned_date", label=_("Commissioned date"))


class PathwayTypePanel(ObjectAttributesPanel):
    """The type-specific attributes of a pathway, limited to the ones its type has.

    Declares every type-specific attribute once; which of them a given
    pathway shows comes from its type's spec in pathway_types.py. Types with
    no attributes of their own render no panel.
    """

    start_face = attrs.ChoiceAttr("start_face", label=_("Start face"))
    end_face = attrs.ChoiceAttr("end_face", label=_("End face"))
    position = attrs.TextAttr("position", label=_("Position in parent"))
    # Conduit bank
    configuration = attrs.ChoiceAttr("configuration", label=_("Configuration"))
    total_conduits = attrs.NumericAttr("total_conduits", label=_("Designed capacity"))
    height = attrs.NumericAttr("height", label=_("Height (rows)"))
    width = attrs.NumericAttr("width", label=_("Width (columns)"))
    encasement_type = attrs.ChoiceAttr("encasement_type", label=_("Encasement type"))
    # Conduit
    material = attrs.ChoiceAttr("material", label=_("Material"))
    inner_diameter = attrs.NumericAttr("inner_diameter", label=_("Inner diameter (mm)"))
    outer_diameter = attrs.NumericAttr("outer_diameter", label=_("Outer diameter (mm)"))
    depth = attrs.NumericAttr("depth", label=_("Depth (m)"))
    start_junction = attrs.RelatedObjectAttr("start_junction", linkify=True, label=_("Start junction"))
    end_junction = attrs.RelatedObjectAttr("end_junction", linkify=True, label=_("End junction"))
    # Aerial span
    aerial_type = attrs.ChoiceAttr("aerial_type", label=_("Aerial type"))
    start_attachment_height = attrs.NumericAttr("start_attachment_height", label=_("Start attachment height (m)"))
    end_attachment_height = attrs.NumericAttr("end_attachment_height", label=_("End attachment height (m)"))
    attachment_height = attrs.NumericAttr("attachment_height", label=_("Attachment height (mean, m)"))
    sag = attrs.NumericAttr("sag", label=_("Sag (m)"))
    messenger_size = attrs.TextAttr("messenger_size", label=_("Messenger size"))
    wind_loading = attrs.TextAttr("wind_loading", label=_("Wind loading"))
    ice_loading = attrs.TextAttr("ice_loading", label=_("Ice loading"))
    # Direct buried
    burial_depth = attrs.NumericAttr("burial_depth", label=_("Burial depth (m)"))
    warning_tape = attrs.BooleanAttr("warning_tape", label=_("Warning tape"))
    tracer_wire = attrs.BooleanAttr("tracer_wire", label=_("Tracer wire"))
    armor_type = attrs.TextAttr("armor_type", label=_("Armor type"))
    # Innerduct
    size = attrs.TextAttr("size", label=_("Size"))
    color = attrs.ColorAttr("color", label=_("Color"))

    # Computed attributes, shown when the field they are computed from applies.
    _derived = {"attachment_height": "start_attachment_height"}

    def get_context(self, context):
        # The layout holds one panel instance for every request, so the
        # attributes to show are worked out per call rather than stored in
        # `only`.
        ctx = super(ObjectAttributesPanel, self).get_context(context)
        obj = ctx["object"]
        rules = PATHWAY_TYPES.get(getattr(obj, "pathway_type", None))
        names = set(rules.fields) if rules else set()
        names |= {name for name, source in self._derived.items() if source in names}
        if rules:
            ctx["title"] = dict(PathwayTypeChoices)[obj.pathway_type]
        ctx["attrs"] = [
            {
                "label": attr.label or self._name_to_label(name),
                "value": attr.render(
                    obj,
                    {"name": name, "perms": ctx["perms"], "preferences": context.get("preferences", {})},
                ),
            }
            for name, attr in self._attrs.items()
            if name in names
        ]
        return ctx

    def should_render(self, context):
        return bool(context["attrs"])


class ConduitJunctionPanel(ObjectAttributesPanel):
    label = attrs.TextAttr("label", label=_("Label"))
    trunk_conduit = attrs.RelatedObjectAttr("trunk_conduit", linkify=True, label=_("Trunk conduit"))
    branch_conduit = attrs.RelatedObjectAttr("branch_conduit", linkify=True, label=_("Branch conduit"))
    towards_structure = attrs.RelatedObjectAttr("towards_structure", linkify=True, label=_("Towards structure"))
    position_on_trunk = attrs.NumericAttr("position_on_trunk", label=_("Position on trunk"))


class PathwayLocationPanel(ObjectAttributesPanel):
    pathway = attrs.RelatedObjectAttr("pathway", linkify=True, label=_("Pathway"))
    site = attrs.RelatedObjectAttr("site", linkify=True, label=_("Site"))
    location = attrs.RelatedObjectAttr("location", linkify=True, label=_("Location"))
    sequence = attrs.NumericAttr("sequence", label=_("Sequence"))


class CableSegmentPanel(ObjectAttributesPanel):
    cable = attrs.RelatedObjectAttr("cable", linkify=True, label=_("Cable"))
    pathway = attrs.RelatedObjectAttr("pathway", linkify=True, label=_("Pathway"))
    sequence = attrs.NumericAttr("sequence", label=_("Sequence"))


class SiteGeometryPanel(ObjectAttributesPanel):
    site = attrs.RelatedObjectAttr("site", linkify=True, label=_("Site"))
    structure = attrs.RelatedObjectAttr("structure", linkify=True, label=_("Structure"))


class CircuitGeometryPanel(ObjectAttributesPanel):
    circuit = attrs.RelatedObjectAttr("circuit", linkify=True, label=_("Circuit"))
    provider_reference = attrs.TextAttr("provider_reference", label=_("Provider Reference"))


class PlannedRoutePanel(ObjectAttributesPanel):
    name = attrs.TextAttr("name", label=_("Name"))
    status = attrs.ChoiceAttr("status", label=_("Status"))
    start_structure = attrs.RelatedObjectAttr("start_structure", linkify=True, label=_("Start structure"))
    end_structure = attrs.RelatedObjectAttr("end_structure", linkify=True, label=_("End structure"))
    start_location = attrs.RelatedObjectAttr("start_location", linkify=True, label=_("Start location"))
    end_location = attrs.RelatedObjectAttr("end_location", linkify=True, label=_("End location"))
    tenant = attrs.RelatedObjectAttr("tenant", linkify=True, label=_("Tenant"))
    cable = attrs.RelatedObjectAttr("cable", linkify=True, label=_("Cable"))
    parent = attrs.RelatedObjectAttr("parent", linkify=True, label=_("Split from"))

import json

from circuits.models import Circuit
from dcim.models import Cable, Location, Site
from django import forms
from django.contrib.gis.forms.widgets import BaseGeometryWidget
from django.contrib.gis.geos import LineString
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.utils.safestring import mark_safe
from netbox.forms import NetBoxModelBulkEditForm, NetBoxModelForm, NetBoxModelImportForm
from tenancy.models import Tenant
from utilities.forms.fields import (
    ColorField,
    CSVChoiceField,
    CSVModelChoiceField,
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
)
from utilities.forms.rendering import FieldSet
from utilities.forms.utils import add_blank_choice, get_field_value
from utilities.forms.widgets import HTMXSelect

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
from .colors import color_to_hex
from .coord_parser import ForgivingGeometryField

# NetBox's ObjectSelectorView resolves `<app_label>.forms.<Model>FilterForm`
# (netbox/views/htmx.py), so every filter form must be importable from this
# module even though they are defined in filterforms.py. Without this, the
# object-selector modal 500s for every model.
from .filterforms import (
    CableSegmentFilterForm,  # noqa: F401
    CircuitGeometryFilterForm,  # noqa: F401
    ConduitJunctionFilterForm,  # noqa: F401
    PathwayFilterForm,  # noqa: F401
    PathwayLocationFilterForm,  # noqa: F401
    PlannedRouteFilterForm,  # noqa: F401
    SiteGeometryFilterForm,  # noqa: F401
    StructureFilterForm,  # noqa: F401
)
from .geo import get_srid, to_leaflet
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
from .pathway_types import PATHWAY_TYPES, TYPE_SPECIFIC_FIELDS, inapplicable_fields

_IMPORT_GEOMETRY_HELP = (
    "GeoJSON, WKT (POINT/LINESTRING), DMS (hemisphere letters optional; lat-first "
    'when omitted), or decimal "lat, lon" pairs (Google Maps order). Interpreted as WGS84.'
)


def _csv_structure_field(side):
    return CSVModelChoiceField(
        queryset=Structure.objects.all(),
        to_field_name="name",
        required=False,
        help_text=f"{side} structure name",
    )


def _csv_location_field(side):
    return CSVModelChoiceField(
        queryset=Location.objects.all(),
        to_field_name="name",
        required=False,
        help_text=f"{side} location name (indoor endpoint)",
    )


def _csv_tenant_field(help_text):
    return CSVModelChoiceField(
        queryset=Tenant.objects.all(),
        to_field_name="name",
        required=False,
        help_text=help_text,
    )


def _csv_status_field(choices):
    return CSVChoiceField(
        choices=choices,
        required=False,
        help_text="Operational status (blank defaults to active)",
    )


class PathwaysMapWidget(BaseGeometryWidget):
    """Map widget using Leaflet + geoman for geometry editing."""

    template_name = "netbox_pathways/widgets/map_widget.html"
    map_srid = 4326
    geom_type = "LINESTRING"  # Default for pathway forms (overrides BaseGeometryWidget 'GEOMETRY')
    endpoint_geojson = None
    # Structure PK the nearby-structures layer must skip -- see StructureForm.
    ref_exclude_pk = None

    class Media:
        css = {
            "all": (
                "netbox_pathways/vendor/leaflet/leaflet.css",
                "netbox_pathways/vendor/geoman/leaflet-geoman.css",
                "netbox_pathways/css/leaflet-theme.css",
            )
        }
        js = (
            "netbox_pathways/vendor/leaflet/leaflet.js",
            "netbox_pathways/vendor/geoman/leaflet-geoman.js",
            "netbox_pathways/dist/pathways-field.min.js",
            "netbox_pathways/dist/endpoint-markers.min.js",
            "netbox_pathways/dist/reference-layer.min.js",
        )

    def __init__(self, geom_type=None, *args, **kwargs):
        if geom_type:
            self.geom_type = geom_type
        super().__init__(*args, **kwargs)

    def serialize(self, value):
        """Emit GeoJSON (not WKT) for JS consumption."""
        return value.geojson if value else ""

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        # Django 6.0 stopped exposing id/name/geom_type at the top level of the
        # widget context (they now live under ``widget``); our template reads
        # them at the top level, so re-expose them here.
        widget = context["widget"]
        context.setdefault("id", widget["attrs"].get("id", ""))
        context.setdefault("name", widget["name"])
        context.setdefault("geom_type", widget["attrs"].get("geom_name", self.geom_type))
        if self.endpoint_geojson:
            context["endpoint_json"] = mark_safe(json.dumps(self.endpoint_geojson))  # noqa: S308
        context["ref_exclude_pk"] = self.ref_exclude_pk
        return context


class PathwayGeometryFallbackMixin:
    """Derive missing geometry from endpoint structures, or accept indoor rows without it.

    Shared by the interactive pathway forms and the CSV import forms so both
    have the same semantics: structure-to-structure entries get a straight
    LineString between the structures, location-to-location (indoor) entries
    need no geometry at all. Pathways with a parent (conduits in banks,
    innerducts) follow the parent's route and need no geometry.
    """

    def selected_pathway_type(self):
        """The pathway type this form is for: cleaned, submitted or initial value, else the instance's."""
        cleaned = getattr(self, "cleaned_data", None) or {}
        if cleaned.get("pathway_type"):
            return cleaned["pathway_type"]
        if "pathway_type" in self.fields and (chosen := get_field_value(self, "pathway_type")):
            return chosen
        return self.instance.pathway_type

    def _derives_geometry(self):
        rules = PATHWAY_TYPES.get(self.selected_pathway_type())
        return bool(rules and rules.derives_geometry)

    def _effective(self, name):
        """The value `name` will hold once this form is saved.

        The cleaned value when the form has the field, otherwise the
        instance's: NetBox's bulk import drops every field a CSV update row
        has no column for, and those keep their stored values.
        """
        if name in self.fields:
            return self.cleaned_data.get(name)
        return getattr(self.instance, name, None)

    def clean(self):
        super().clean()
        cleaned = self.cleaned_data
        if self._effective("geometry"):
            return cleaned

        # Pathways with a parent (a conduit in a bank, an innerduct) follow
        # the parent's route; never synthesize standalone geometry for them.
        if self._effective("parent"):
            return cleaned
        # Types that derive their own geometry from the endpoints (aerial spans)
        # build it in Pathway.clean(); a synthesized centroid line would be wrong.
        if self._derives_geometry():
            return cleaned

        start_struct = self._effective("start_structure")
        end_struct = self._effective("end_structure")
        start_loc = self._effective("start_location")
        end_loc = self._effective("end_location")

        # Indoor pathway (both endpoints are locations): no geometry exists
        if start_loc and end_loc and not start_struct and not end_struct:
            return cleaned

        # Auto-generate geometry from structures
        if start_struct and end_struct and start_struct.geometry and end_struct.geometry:
            start_geom = start_struct.geometry
            end_geom = end_struct.geometry
            start_pt = start_geom.centroid if start_geom.geom_type != "Point" else start_geom
            end_pt = end_geom.centroid if end_geom.geom_type != "Point" else end_geom
            line = LineString((start_pt.x, start_pt.y), (end_pt.x, end_pt.y), srid=get_srid())
            if "geometry" in self.fields:
                cleaned["geometry"] = line
            else:
                self.instance.geometry = line
        elif "geometry" in self.fields:
            raise ValidationError(
                {
                    "geometry": "Geometry is required unless both endpoints are structures "
                    "(auto-generated) or both are locations (indoor)."
                }
            )
        # Without a geometry field, Pathway.clean() reports the missing route.
        return cleaned


class PathwayEndpointFormMixin(PathwayGeometryFallbackMixin):
    """Mixin for pathway forms: auto-generates geometry from structures, injects it for the widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "geometry" in self.fields:
            self.fields["geometry"].required = False
        self._inject_endpoint_geometry()

    def _inject_endpoint_geometry(self):
        """Serialize anchor structure geometry (and names, for labels) into the widget.

        Types that derive straight geometry (aerial spans) also ask the widget
        for straight mode, even before any endpoint is chosen.
        """
        if "geometry" not in self.fields:
            return
        endpoint_data = {}
        if self._derives_geometry():
            endpoint_data["straight"] = True
        for side in ("start", "end"):
            structure = self.instance.anchor_structure(side)
            if structure and structure.geometry:
                geom_4326 = to_leaflet(structure.geometry)
                endpoint_data[side] = json.loads(geom_4326.geojson)
                endpoint_data[f"{side}_name"] = structure.name
        widget = self.fields["geometry"].widget
        widget.endpoint_geojson = endpoint_data if endpoint_data else None


def _resolve_initial_parent(form, field_name):
    """Resolve a parent object from a pk passed in form initial data.

    Reads the queryset from the form field itself (`form.fields[field_name].queryset`)
    rather than taking one as an argument, since the field already declares it.
    Returns None when editing an existing object, when the initial is
    absent, or when the pk does not resolve to a row.
    """
    if form.instance.pk:
        return None
    raw = form.initial.get(field_name)
    if not raw:
        return None
    queryset = form.fields[field_name].queryset
    try:
        return queryset.get(pk=raw)
    except (queryset.model.DoesNotExist, ValueError, TypeError):
        return None


def _prefill_initial_from_parent(form, parent, field_names):
    """Copy parent attribute values into form initial for absent keys.

    Values already present in initial (explicit GET params) always win.
    FK values are stored as pks so dynamic choice fields render them.
    """
    for name in field_names:
        if form.initial.get(name) not in (None, ""):
            continue
        value = getattr(parent, name, None)
        if value in (None, ""):
            continue
        form.initial[name] = value.pk if hasattr(value, "pk") else value


# --- Structure ---


class StructureForm(NetBoxModelForm):
    site = DynamicModelChoiceField(queryset=Site.objects.all(), required=False, selector=True, quick_add=True)
    location = DynamicModelChoiceField(
        queryset=Location.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
        query_params={"site_id": "$site"},
    )
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True, quick_add=True)
    installed_by = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
        label="Installed by",
        help_text="Contractor or workforce that physically installed this structure",
    )

    fieldsets = (
        FieldSet("name", "status", "structure_type", "site", "location", "tenant", name="Structure"),
        FieldSet("installed_by", "installation_date", "commissioned_date", name="Lifecycle"),
        FieldSet("height", "width", "length", "depth", "elevation", name="Dimensions"),
        FieldSet("geometry", name="Geometry"),
        FieldSet("access_notes", "tags", name="Details"),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # This structure is in the widget's nearby-structures fetch too. Tell
        # the layer to skip it, or its faded read-only copy sits under the
        # editable marker and stays behind as a ghost once the marker moves.
        if self.instance.pk:
            self.fields["geometry"].widget.ref_exclude_pk = self.instance.pk

    class Meta:
        model = Structure
        fields = [
            "name",
            "status",
            "structure_type",
            "site",
            "location",
            "tenant",
            "installed_by",
            "geometry",
            "height",
            "width",
            "length",
            "depth",
            "elevation",
            "installation_date",
            "commissioned_date",
            "access_notes",
            "comments",
            "tags",
        ]
        widgets = {
            "geometry": PathwaysMapWidget(geom_type="Geometry"),
        }


class StructureImportForm(NetBoxModelImportForm):
    status = _csv_status_field(StructureStatusChoices)
    site = CSVModelChoiceField(
        queryset=Site.objects.all(),
        to_field_name="name",
        required=False,
        help_text="Site name",
    )
    tenant = CSVModelChoiceField(
        queryset=Tenant.objects.all(),
        to_field_name="name",
        required=False,
        help_text="Tenant name",
    )
    installed_by = _csv_tenant_field("Installer tenant name")
    location = CSVModelChoiceField(
        queryset=Location.objects.all(),
        to_field_name="name",
        required=False,
        help_text="Location name",
    )
    geometry = ForgivingGeometryField(
        required=False,
        srid=get_srid(),
        help_text=_IMPORT_GEOMETRY_HELP,
    )

    class Meta:
        model = Structure
        fields = [
            "name",
            "status",
            "structure_type",
            "site",
            "location",
            "tenant",
            "installed_by",
            "height",
            "width",
            "length",
            "depth",
            "elevation",
            "installation_date",
            "commissioned_date",
            "geometry",
            "access_notes",
            "comments",
        ]


class StructureBulkEditForm(NetBoxModelBulkEditForm):
    site = DynamicModelChoiceField(queryset=Site.objects.all(), required=False, selector=True)
    location = DynamicModelChoiceField(
        queryset=Location.objects.all(),
        required=False,
        selector=True,
        query_params={"site_id": "$site"},
    )
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True)
    installed_by = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True)
    status = forms.ChoiceField(choices=StructureStatusChoices, required=False)
    structure_type = forms.ChoiceField(choices=StructureTypeChoices, required=False)
    commissioned_date = forms.DateField(required=False)

    model = Structure
    fieldsets = (
        FieldSet("status", "site", "location", "structure_type", "tenant", name="Structure"),
        FieldSet("installed_by", "commissioned_date", name="Lifecycle"),
    )
    nullable_fields = ("site", "location", "tenant", "installed_by", "commissioned_date", "access_notes")


# --- Pathway ---

# Columns every pathway has, whatever its type. `parent` is here too: it is
# hidden for types that cannot have one, not cleared.
_COMMON_PATHWAY_FIELDS = (
    "pathway_type",
    "parent",
    "label",
    "status",
    "geometry",
    "start_structure",
    "end_structure",
    "start_location",
    "end_location",
    "tenant",
    "installed_by",
    "length",
    "installation_date",
    "commissioned_date",
    "comments",
)
_ENDPOINT_FIELDS = ("start_structure", "end_structure", "start_location", "end_location")
_LIFECYCLE_FIELDS = ("installed_by", "installation_date", "commissioned_date")
# Every type-specific column once, in pathway_types.py order.
_TYPE_FIELDS = tuple(dict.fromkeys(name for rules in PATHWAY_TYPES.values() for name in rules.fields))
# Type-specific columns shown in a shared fieldset rather than the type's own.
_SHARED_FIELDSET_FIELDS = frozenset({"position", "start_face", "end_face", "start_junction", "end_junction"})
# An innerduct is pulled into a duct that is already there, so it does not
# take its parent's installer and dates; anything else is built with its parent.
_NO_LIFECYCLE_PREFILL = frozenset({"innerduct"})
_TYPE_LABELS = dict(PathwayTypeChoices)


def _type_fieldsets(names):
    """One fieldset per pathway type, holding that type's fields from `names`.

    A field shared by several types is shown once, under the first type in
    pathway_types.py that has it.
    """
    placed = set()
    fieldsets = []
    for pathway_type, rules in PATHWAY_TYPES.items():
        own = [name for name in rules.fields if name in names and name not in placed]
        placed.update(own)
        if own:
            fieldsets.append(FieldSet(*own, name=_TYPE_LABELS[pathway_type]))
    return fieldsets


def _pathway_fieldsets(pathway_type, fields):
    """Fieldsets for a pathway form showing `fields` of `pathway_type`."""

    def present(*names):
        return [name for name in names if name in fields]

    fieldsets = [FieldSet("pathway_type", "label", "status", "tenant", "length", name="Pathway")]
    if hierarchy := present("parent", "position"):
        fieldsets.append(FieldSet(*hierarchy, name="Parent"))
    fieldsets.append(FieldSet(*_LIFECYCLE_FIELDS, name="Lifecycle"))
    fieldsets.append(FieldSet(*_ENDPOINT_FIELDS, *present("start_face", "end_face"), name="Endpoints"))
    if junctions := present("start_junction", "end_junction"):
        fieldsets.append(FieldSet(*junctions, name="Junctions"))
    rules = PATHWAY_TYPES.get(pathway_type)
    if rules and (attributes := [name for name in rules.fields if name not in _SHARED_FIELDSET_FIELDS]):
        fieldsets.append(FieldSet(*attributes, name=_TYPE_LABELS[pathway_type]))
    fieldsets.append(FieldSet("geometry", name="Geometry"))
    fieldsets.append(FieldSet("tags", name="Details"))
    return tuple(fieldsets)


class PathwayForm(PathwayEndpointFormMixin, NetBoxModelForm):
    """Add/edit form for every pathway type.

    The chosen type decides which fields the form has: changing it
    re-renders the form (HTMXSelect), and the type comes from the submitted
    data, the initial data (`?pathway_type=`) or the instance, in that order.
    """

    parent = DynamicModelChoiceField(
        queryset=Pathway.objects.all(),
        required=False,
        selector=True,
        help_text="Pathway this one runs inside",
    )
    start_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
    )
    end_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
    )
    start_location = DynamicModelChoiceField(
        queryset=Location.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
    )
    end_location = DynamicModelChoiceField(
        queryset=Location.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
    )
    start_junction = DynamicModelChoiceField(
        queryset=ConduitJunction.objects.all(),
        required=False,
        selector=True,
    )
    end_junction = DynamicModelChoiceField(
        queryset=ConduitJunction.objects.all(),
        required=False,
        selector=True,
    )
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True, quick_add=True)
    installed_by = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
        label="Installed by",
    )

    class Meta:
        model = Pathway
        fields = [*_COMMON_PATHWAY_FIELDS, *_TYPE_FIELDS, "tags"]
        widgets = {
            "pathway_type": HTMXSelect(),
            "geometry": PathwaysMapWidget(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        pathway_type = self.selected_pathway_type()
        rules = PATHWAY_TYPES.get(pathway_type)
        hidden = set(inapplicable_fields(pathway_type)) if rules else set(TYPE_SPECIFIC_FIELDS)
        # A pathway retyped to a type that cannot have a parent keeps the
        # field while it still has one, so the containment error has a field
        # to land on and the user can clear the parent there.
        if rules is None or not (rules.parents or self.instance.parent_id):
            hidden.add("parent")
        for name in hidden:
            del self.fields[name]
        if "parent" in self.fields:
            self.fields["parent"].required = rules.parent_required
            self.fields["parent"].widget.add_query_params({"pathway_type": sorted(rules.parents)})
        self._parent_prefilled = "parent" not in self.fields
        self.fieldsets = _pathway_fieldsets(pathway_type, self.fields)

    def get_initial_for_field(self, field, field_name):
        # The parent is read when the form first renders, not in __init__:
        # the edit view narrows the parent field to the pathways the user
        # may view only after building the form, and reading it earlier
        # would copy values from a parent the user cannot see. (__init__
        # itself reads the chosen type through here, before the flag exists.)
        if not getattr(self, "_parent_prefilled", True):
            self._parent_prefilled = True
            self._prefill_from_parent(self.selected_pathway_type())
        return super().get_initial_for_field(field, field_name)

    def _prefill_from_parent(self, pathway_type):
        """Fill a new pathway's blank fields from the parent named in the initial data.

        The endpoints, the type-specific fields both types have (except the
        slot, `position`) and, unless excluded above, the lifecycle fields.
        Tenant and geometry are never copied. The parent is looked up in the
        parent field's queryset, so only a pathway the user may view is read.
        """
        parent = _resolve_initial_parent(self, "parent")
        if parent is None:
            return
        parent_rules = PATHWAY_TYPES.get(parent.pathway_type)
        shared = [name for name in parent_rules.fields if name in self.fields] if parent_rules else []
        names = [*_ENDPOINT_FIELDS, *(name for name in shared if name != "position")]
        if pathway_type not in _NO_LIFECYCLE_PREFILL:
            names += _LIFECYCLE_FIELDS
        _prefill_initial_from_parent(self, parent, names)


class PathwayImportForm(PathwayGeometryFallbackMixin, NetBoxModelImportForm):
    pathway_type = CSVChoiceField(choices=PathwayTypeChoices, help_text="Pathway type")
    status = _csv_status_field(PathwayStatusChoices)
    parent = CSVModelChoiceField(
        queryset=Pathway.objects.all(),
        required=False,
        help_text="Parent pathway ID (numeric)",
    )
    start_structure = _csv_structure_field("Starting")
    end_structure = _csv_structure_field("Ending")
    start_location = _csv_location_field("Starting")
    end_location = _csv_location_field("Ending")
    start_junction = CSVModelChoiceField(
        queryset=ConduitJunction.objects.all(),
        to_field_name="label",
        required=False,
        help_text="Starting junction label",
    )
    end_junction = CSVModelChoiceField(
        queryset=ConduitJunction.objects.all(),
        to_field_name="label",
        required=False,
        help_text="Ending junction label",
    )
    tenant = _csv_tenant_field("Owner tenant name")
    installed_by = _csv_tenant_field("Installer tenant name")
    color = forms.CharField(
        required=False,
        max_length=16,
        help_text='Color name (e.g. "Blue") or hex code (e.g. "2196f3")',
    )
    geometry = ForgivingGeometryField(
        required=False,
        srid=get_srid(),
        geom_type="LINESTRING",
        help_text=_IMPORT_GEOMETRY_HELP,
    )

    def clean_color(self):
        # Colors used to be free text, so imports that still name them keep
        # working; anything unrecognized is an error rather than a silently
        # blank field.
        color = self.cleaned_data.get("color")
        hex_code = color_to_hex(color)
        if hex_code is None:
            raise forms.ValidationError(f'"{color}" is not a known color name or hex code')
        return hex_code

    def add_error(self, field, error):
        """Report an error on a column this row does not carry against the row.

        On an update NetBox's bulk import drops the fields the CSV has no
        column for, but Pathway.clean() still names the field at fault (a
        retype that leaves a parent the new type cannot have faults
        `parent`). Django refuses an error on a field the form lacks.
        """
        if field is None and hasattr(error, "error_dict"):
            errors = {}
            for name, messages in error.error_dict.items():
                if name == NON_FIELD_ERRORS or name in self.fields:
                    errors.setdefault(name, []).extend(messages)
                else:
                    errors.setdefault(NON_FIELD_ERRORS, []).extend(
                        ValidationError(f"{name}: {text}") for message in messages for text in message.messages
                    )
            error = ValidationError(errors)
        super().add_error(field, error)

    class Meta:
        model = Pathway
        fields = [*_COMMON_PATHWAY_FIELDS, *_TYPE_FIELDS]


class PathwayBulkEditForm(NetBoxModelBulkEditForm):
    parent = DynamicModelChoiceField(queryset=Pathway.objects.all(), required=False, selector=True)
    status = forms.ChoiceField(choices=add_blank_choice(PathwayStatusChoices), required=False)
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True)
    installed_by = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True)
    commissioned_date = forms.DateField(required=False)
    start_face = forms.ChoiceField(choices=add_blank_choice(BankFaceChoices), required=False)
    end_face = forms.ChoiceField(choices=add_blank_choice(BankFaceChoices), required=False)
    configuration = forms.ChoiceField(choices=add_blank_choice(ConduitBankConfigChoices), required=False)
    encasement_type = forms.ChoiceField(choices=add_blank_choice(EncasementTypeChoices), required=False)
    height = forms.IntegerField(required=False, min_value=1)
    width = forms.IntegerField(required=False, min_value=1)
    material = forms.ChoiceField(choices=add_blank_choice(ConduitMaterialChoices), required=False)
    aerial_type = forms.ChoiceField(choices=add_blank_choice(AerialTypeChoices), required=False)
    messenger_size = forms.CharField(max_length=50, required=False)
    wind_loading = forms.CharField(max_length=50, required=False)
    ice_loading = forms.CharField(max_length=50, required=False)
    warning_tape = forms.NullBooleanField(required=False)
    tracer_wire = forms.NullBooleanField(required=False)
    armor_type = forms.CharField(max_length=100, required=False)
    size = forms.CharField(max_length=50, required=False)
    color = ColorField(required=False)

    model = Pathway
    # Type-specific values only stick on pathways of a type they apply to;
    # Pathway.save() clears them on the others.
    fieldsets = (
        FieldSet("status", "tenant", "parent", name="Pathway"),
        FieldSet("installed_by", "commissioned_date", name="Lifecycle"),
        *_type_fieldsets(
            {
                "start_face",
                "end_face",
                "configuration",
                "encasement_type",
                "height",
                "width",
                "material",
                "aerial_type",
                "messenger_size",
                "wind_loading",
                "ice_loading",
                "warning_tape",
                "tracer_wire",
                "armor_type",
                "size",
                "color",
            }
        ),
    )
    nullable_fields = (
        "parent",
        "tenant",
        "installed_by",
        "commissioned_date",
        "start_face",
        "end_face",
        "configuration",
        "encasement_type",
        "height",
        "width",
        "material",
        "aerial_type",
        "messenger_size",
        "wind_loading",
        "ice_loading",
        "armor_type",
        "size",
        "color",
    )


# --- Conduit Junction ---


# Only conduits may be a junction's trunk or branch (the model checks it too).
_JUNCTION_CONDUITS = Pathway.objects.filter(pathway_type="conduit")


class ConduitJunctionForm(NetBoxModelForm):
    trunk_conduit = DynamicModelChoiceField(
        queryset=_JUNCTION_CONDUITS,
        selector=True,
        query_params={"pathway_type": "conduit"},
    )
    branch_conduit = DynamicModelChoiceField(
        queryset=_JUNCTION_CONDUITS,
        selector=True,
        query_params={"pathway_type": "conduit"},
    )
    towards_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(),
        selector=True,
        quick_add=True,
    )

    fieldsets = (
        FieldSet("label", name="Junction"),
        FieldSet("trunk_conduit", "branch_conduit", "towards_structure", "position_on_trunk", name="Configuration"),
        FieldSet("tags", name="Details"),
    )

    class Meta:
        model = ConduitJunction
        fields = [
            "label",
            "trunk_conduit",
            "branch_conduit",
            "towards_structure",
            "position_on_trunk",
            "comments",
            "tags",
        ]


class ConduitJunctionImportForm(NetBoxModelImportForm):
    trunk_conduit = CSVModelChoiceField(
        queryset=_JUNCTION_CONDUITS,
        help_text="Trunk conduit ID (numeric)",
    )
    branch_conduit = CSVModelChoiceField(
        queryset=_JUNCTION_CONDUITS,
        help_text="Branch conduit ID (numeric)",
    )
    towards_structure = CSVModelChoiceField(
        queryset=Structure.objects.all(),
        to_field_name="name",
        help_text="Name of the trunk endpoint structure the junction faces",
    )

    class Meta:
        model = ConduitJunction
        fields = [
            "label",
            "trunk_conduit",
            "branch_conduit",
            "towards_structure",
            "position_on_trunk",
            "comments",
        ]


# --- Cable Segment ---


class CableSegmentForm(NetBoxModelForm):
    cable = DynamicModelChoiceField(queryset=Cable.objects.all(), selector=True)
    pathway = DynamicModelChoiceField(
        queryset=Pathway.objects.all(),
        required=False,
        selector=True,
    )
    lashed_with = DynamicModelMultipleChoiceField(
        queryset=CableSegment.objects.all(),
        required=False,
        label="Lashed with",
        help_text="Other cable segments mechanically lashed together with this one (symmetrical).",
    )

    fieldsets = (
        FieldSet("cable", "pathway", "lashed_with", name="Cable Segment"),
        FieldSet("tags", name="Details"),
    )

    class Meta:
        model = CableSegment
        fields = [
            "cable",
            "pathway",
            "lashed_with",
            "comments",
            "tags",
        ]


class CableSegmentImportForm(NetBoxModelImportForm):
    class Meta:
        model = CableSegment
        # M2M `lashed_with` is intentionally omitted from CSV import; populate it
        # via the UI form or REST API after the segments themselves are imported.
        fields = [
            "cable",
            "pathway",
            "sequence",
            "comments",
        ]


class CableSegmentBulkEditForm(NetBoxModelBulkEditForm):
    pathway = DynamicModelChoiceField(
        queryset=Pathway.objects.all(),
        required=False,
        selector=True,
    )

    model = CableSegment
    fieldsets = (FieldSet("pathway"),)
    nullable_fields = ("pathway",)


class RouteSegmentForm(forms.Form):
    """Inline pathway picker for the cable Route tab.

    A plain Form rather than a ModelForm: the Route tab creates segments
    through an HTMX partial that assigns `sequence` itself, and the form's job
    is only to validate the chosen pathway. Either `connected_to` (explicit
    graph nodes) or `cable_end_ref` (`<cable_pk>:A|B`, which the API resolves
    to the cable end's candidate nodes itself) filters the picker to the
    pathways reachable from this point in the route; `cable_end_ref` wins when
    both are given. Neither restricts what POST accepts, because the user may
    have widened the list with Show all pathways.
    """

    pathway = DynamicModelChoiceField(
        queryset=Pathway.objects.all(),
        label="Pathway",
    )
    after_sequence = forms.IntegerField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, connected_to=None, cable_end_ref=None, **kwargs):
        super().__init__(*args, **kwargs)
        if cable_end_ref:
            # One param regardless of how many structures the site holds.
            self.fields["pathway"].widget.add_query_param("connected_to_cable_end", cable_end_ref)
        elif connected_to:
            self.fields["pathway"].widget.add_query_param(
                "connected_to",
                [f"{kind}:{pk}" for kind, pk in connected_to],
            )


# --- Pathway Location ---


class PathwayLocationForm(NetBoxModelForm):
    pathway = DynamicModelChoiceField(
        queryset=Pathway.objects.all(),
        selector=True,
    )
    site = DynamicModelChoiceField(
        queryset=Site.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
    )
    location = DynamicModelChoiceField(
        queryset=Location.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
    )

    fieldsets = (
        FieldSet("pathway", "site", "location", "sequence", name="Waypoint"),
        FieldSet("tags", name="Details"),
    )

    class Meta:
        model = PathwayLocation
        fields = [
            "pathway",
            "site",
            "location",
            "sequence",
            "comments",
            "tags",
        ]


# --- Site Geometry ---


class SiteGeometryForm(NetBoxModelForm):
    site = DynamicModelChoiceField(
        queryset=Site.objects.all(),
        selector=True,
        quick_add=True,
    )
    structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
    )

    fieldsets = (
        FieldSet("site", "structure", name="Site Geometry"),
        FieldSet("geometry", name="Geometry"),
        FieldSet("tags", name="Details"),
    )

    class Meta:
        model = SiteGeometry
        fields = ["site", "structure", "geometry", "comments", "tags"]
        widgets = {
            "geometry": PathwaysMapWidget(geom_type="Geometry"),
        }


class SiteGeometryImportForm(NetBoxModelImportForm):
    site = CSVModelChoiceField(
        queryset=Site.objects.all(),
        to_field_name="name",
        help_text="Site name",
    )
    structure = CSVModelChoiceField(
        queryset=Structure.objects.all(),
        to_field_name="name",
        required=False,
        help_text="Structure that physically represents this site",
    )
    geometry = ForgivingGeometryField(
        required=False,
        srid=get_srid(),
        help_text=_IMPORT_GEOMETRY_HELP,
    )

    class Meta:
        model = SiteGeometry
        fields = ["site", "structure", "geometry", "comments"]


# --- Circuit Geometry ---


class CircuitGeometryForm(NetBoxModelForm):
    circuit = DynamicModelChoiceField(
        queryset=Circuit.objects.all(),
        selector=True,
    )

    fieldsets = (
        FieldSet("circuit", "provider_reference", name="Circuit Route"),
        FieldSet("path", name="Route Geometry"),
        FieldSet("tags", name="Details"),
    )

    class Meta:
        model = CircuitGeometry
        fields = ["circuit", "path", "provider_reference", "comments", "tags"]
        widgets = {
            "path": PathwaysMapWidget(),
        }


class CircuitGeometryImportForm(NetBoxModelImportForm):
    circuit = CSVModelChoiceField(
        queryset=Circuit.objects.all(),
        help_text="Circuit ID (numeric)",
    )
    path = ForgivingGeometryField(
        srid=get_srid(),
        geom_type="LINESTRING",
        help_text=_IMPORT_GEOMETRY_HELP,
    )

    class Meta:
        model = CircuitGeometry
        fields = ["circuit", "path", "provider_reference", "comments"]


# --- Planned Route ---


class PlannedRouteForm(NetBoxModelForm):
    start_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        selector=True,
    )
    end_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        selector=True,
    )
    start_location = DynamicModelChoiceField(
        queryset=Location.objects.all(),
        required=False,
        selector=True,
    )
    end_location = DynamicModelChoiceField(
        queryset=Location.objects.all(),
        required=False,
        selector=True,
    )
    tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        selector=True,
    )
    cable = DynamicModelChoiceField(
        queryset=Cable.objects.all(),
        required=False,
        selector=True,
    )

    fieldsets = (
        FieldSet("name", "status", "tenant", name="Planned Route"),
        FieldSet("start_structure", "start_location", "end_structure", "end_location", name="Endpoints"),
        FieldSet("cable", name="Assignment"),
        FieldSet("tags", name="Details"),
    )

    class Meta:
        model = PlannedRoute
        fields = [
            "name",
            "status",
            "start_structure",
            "start_location",
            "end_structure",
            "end_location",
            "tenant",
            "cable",
            "comments",
            "tags",
        ]


class PlannedRouteImportForm(NetBoxModelImportForm):
    start_structure = _csv_structure_field("Starting")
    end_structure = _csv_structure_field("Ending")
    start_location = _csv_location_field("Starting")
    end_location = _csv_location_field("Ending")
    tenant = CSVModelChoiceField(
        queryset=Tenant.objects.all(),
        to_field_name="name",
        required=False,
        help_text="Tenant name",
    )
    cable = CSVModelChoiceField(
        queryset=Cable.objects.all(),
        required=False,
        help_text="Cable ID (numeric)",
    )

    class Meta:
        model = PlannedRoute
        fields = [
            "name",
            "status",
            "start_structure",
            "end_structure",
            "start_location",
            "end_location",
            "tenant",
            "cable",
            "comments",
        ]


class PlannedRouteBulkEditForm(NetBoxModelBulkEditForm):
    status = forms.ChoiceField(choices=PlannedRouteStatusChoices, required=False)
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True)

    model = PlannedRoute
    fieldsets = (FieldSet("status", "tenant"),)
    nullable_fields = ("tenant",)


# --- Route Planner ---


class RoutePlannerEndpointForm(forms.Form):
    """Endpoint selection for the route planner."""

    start_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        label="Start Structure",
        context={"disabled": "no_pathways", "description": "description"},
    )
    end_structure = DynamicModelChoiceField(
        queryset=Structure.objects.all(),
        required=False,
        label="End Structure",
        context={"disabled": "no_pathways", "description": "description"},
    )


class PlannedRouteApplyForm(forms.Form):
    """Cable selection for applying a planned route."""

    cable = DynamicModelChoiceField(
        queryset=Cable.objects.all(),
        required=True,
        label="Cable",
    )

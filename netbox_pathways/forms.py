import json

from circuits.models import Circuit
from dcim.models import Cable, Location, Site
from django import forms
from django.contrib.gis.forms.widgets import BaseGeometryWidget
from django.contrib.gis.geos import LineString
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

from .choices import (
    AerialTypeChoices,
    BankFaceChoices,
    ConduitBankConfigChoices,
    ConduitMaterialChoices,
    EncasementTypeChoices,
    PathwayStatusChoices,
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
    AerialSpanFilterForm,  # noqa: F401
    CableSegmentFilterForm,  # noqa: F401
    CircuitGeometryFilterForm,  # noqa: F401
    ConduitBankFilterForm,  # noqa: F401
    ConduitFilterForm,  # noqa: F401
    ConduitJunctionFilterForm,  # noqa: F401
    DirectBuriedFilterForm,  # noqa: F401
    InnerductFilterForm,  # noqa: F401
    PathwayFilterForm,  # noqa: F401
    PathwayLocationFilterForm,  # noqa: F401
    PlannedRouteFilterForm,  # noqa: F401
    SiteGeometryFilterForm,  # noqa: F401
    StructureFilterForm,  # noqa: F401
)
from .geo import get_srid, to_leaflet
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
        # them at the top level, so re-expose them here. setdefault keeps this
        # backwards compatible with Django <= 5.2, which still sets them.
        widget = context["widget"]
        context.setdefault("id", widget["attrs"].get("id", ""))
        context.setdefault("name", widget["name"])
        context.setdefault("geom_type", widget["attrs"].get("geom_name", self.geom_type))
        if self.endpoint_geojson:
            context["endpoint_json"] = mark_safe(json.dumps(self.endpoint_geojson))  # noqa: S308
        context["ref_exclude_pk"] = self.ref_exclude_pk
        return context


class PathwayPathFallbackMixin:
    """Derive a missing path from endpoint structures, or accept pathless indoor rows.

    Shared by the interactive pathway forms and the CSV import forms so both
    have the same semantics: structure-to-structure entries get a straight
    LineString between the structures, location-to-location (indoor) entries
    need no geographic path at all. Contained pathways (conduits in banks,
    innerducts) follow the parent's route and need no path.
    """

    def clean(self):
        super().clean()
        cleaned = self.cleaned_data
        path = cleaned.get("path")
        if path:
            return cleaned

        # Contained pathways (a conduit in a bank, an innerduct) follow the
        # parent's route; never synthesize a standalone path for them.
        if cleaned.get("conduit_bank") or cleaned.get("parent_conduit"):
            return cleaned

        start_struct = cleaned.get("start_structure")
        end_struct = cleaned.get("end_structure")
        start_loc = cleaned.get("start_location")
        end_loc = cleaned.get("end_location")

        # Indoor pathway (both endpoints are locations): no geographic path exists
        if start_loc and end_loc and not start_struct and not end_struct:
            return cleaned

        # Auto-generate path from structures
        if start_struct and end_struct and start_struct.geometry and end_struct.geometry:
            start_geom = start_struct.geometry
            end_geom = end_struct.geometry
            start_pt = start_geom.centroid if start_geom.geom_type != "Point" else start_geom
            end_pt = end_geom.centroid if end_geom.geom_type != "Point" else end_geom
            cleaned["path"] = LineString(
                (start_pt.x, start_pt.y),
                (end_pt.x, end_pt.y),
                srid=get_srid(),
            )
        else:
            from django.core.exceptions import ValidationError

            raise ValidationError(
                {
                    "path": "Path is required unless both endpoints are structures "
                    "(auto-generated) or both are locations (indoor)."
                }
            )

        return cleaned


class PathwayEndpointFormMixin(PathwayPathFallbackMixin):
    """Mixin for pathway forms: auto-generates path from structures, injects geometry for widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "path" in self.fields:
            self.fields["path"].required = False
        self._inject_endpoint_geometry()

    def _inject_endpoint_geometry(self):
        """Serialize structure geometry (and names, for labels) into the widget."""
        if "path" not in self.fields:
            return
        endpoint_data = {}
        for side in ("start", "end"):
            structure = getattr(self.instance, f"{side}_structure", None)
            if structure and structure.geometry:
                geom_4326 = to_leaflet(structure.geometry)
                endpoint_data[side] = json.loads(geom_4326.geojson)
                endpoint_data[f"{side}_name"] = structure.name
        widget = self.fields["path"].widget
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


# --- Pathway (base) ---


class PathwayForm(PathwayEndpointFormMixin, NetBoxModelForm):
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
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True, quick_add=True)
    installed_by = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
        label="Installed by",
    )

    fieldsets = (
        FieldSet("label", "status", "tenant", "length", name="Pathway"),
        FieldSet("installed_by", "installation_date", "commissioned_date", name="Lifecycle"),
        FieldSet("start_structure", "end_structure", "start_location", "end_location", name="Endpoints"),
        FieldSet("path", name="Geometry"),
        FieldSet("tags", name="Details"),
    )

    class Meta:
        model = Pathway
        fields = [
            "label",
            "status",
            "path",
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
            "tags",
        ]
        widgets = {
            "path": PathwaysMapWidget(),
        }


# --- Conduit ---


class ConduitForm(PathwayEndpointFormMixin, NetBoxModelForm):
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
    start_face = forms.ChoiceField(choices=BankFaceChoices, required=False)
    end_face = forms.ChoiceField(choices=BankFaceChoices, required=False)
    conduit_bank = DynamicModelChoiceField(
        queryset=ConduitBank.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
    )
    start_junction = DynamicModelChoiceField(
        queryset=ConduitJunction.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
    )
    end_junction = DynamicModelChoiceField(
        queryset=ConduitJunction.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
    )

    installed_by = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
        label="Installed by",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        bank = _resolve_initial_parent(self, "conduit_bank")
        if bank:
            _prefill_initial_from_parent(
                self,
                bank,
                [
                    "start_structure",
                    "end_structure",
                    "start_location",
                    "end_location",
                    "start_face",
                    "end_face",
                    "installed_by",
                    "installation_date",
                    "commissioned_date",
                ],
            )

    fieldsets = (
        FieldSet("label", "status", "material", "length", name="Conduit"),
        FieldSet("installed_by", "installation_date", "commissioned_date", name="Lifecycle"),
        FieldSet(
            "start_structure",
            "end_structure",
            "start_location",
            "end_location",
            "start_face",
            "end_face",
            name="Endpoints",
        ),
        FieldSet("start_junction", "end_junction", name="Junctions"),
        FieldSet("inner_diameter", "outer_diameter", "depth", name="Dimensions"),
        FieldSet("conduit_bank", "bank_position", name="Conduit Bank"),
        FieldSet("path", name="Geometry"),
        FieldSet("tags", name="Details"),
    )

    class Meta:
        model = Conduit
        fields = [
            "label",
            "status",
            "material",
            "path",
            "start_structure",
            "end_structure",
            "start_location",
            "end_location",
            "start_face",
            "end_face",
            "start_junction",
            "end_junction",
            "inner_diameter",
            "outer_diameter",
            "depth",
            "conduit_bank",
            "bank_position",
            "length",
            "installed_by",
            "installation_date",
            "commissioned_date",
            "comments",
            "tags",
        ]
        widgets = {
            "path": PathwaysMapWidget(),
        }


class ConduitImportForm(PathwayPathFallbackMixin, NetBoxModelImportForm):
    status = _csv_status_field(PathwayStatusChoices)
    start_structure = _csv_structure_field("Starting")
    end_structure = _csv_structure_field("Ending")
    start_location = _csv_location_field("Starting")
    end_location = _csv_location_field("Ending")
    conduit_bank = CSVModelChoiceField(
        queryset=ConduitBank.objects.all(),
        to_field_name="label",
        required=False,
        help_text="Parent conduit bank label",
    )
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
    path = ForgivingGeometryField(
        required=False,
        srid=get_srid(),
        geom_type="LINESTRING",
        help_text=_IMPORT_GEOMETRY_HELP,
    )

    class Meta:
        model = Conduit
        fields = [
            "label",
            "status",
            "material",
            "start_structure",
            "start_face",
            "end_structure",
            "end_face",
            "start_location",
            "end_location",
            "start_junction",
            "end_junction",
            "conduit_bank",
            "bank_position",
            "inner_diameter",
            "outer_diameter",
            "depth",
            "length",
            "tenant",
            "installed_by",
            "installation_date",
            "commissioned_date",
            "path",
            "comments",
        ]


class ConduitBulkEditForm(NetBoxModelBulkEditForm):
    status = forms.ChoiceField(choices=PathwayStatusChoices, required=False)
    material = forms.ChoiceField(choices=ConduitMaterialChoices, required=False)
    installed_by = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True)
    commissioned_date = forms.DateField(required=False)

    model = Conduit
    fieldsets = (
        FieldSet("status", "material", name="Conduit"),
        FieldSet("installed_by", "commissioned_date", name="Lifecycle"),
    )
    nullable_fields = ("material", "installed_by", "commissioned_date")


# --- Aerial Span ---


class AerialSpanForm(PathwayEndpointFormMixin, NetBoxModelForm):
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

    installed_by = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
        label="Installed by",
    )

    fieldsets = (
        FieldSet("label", "status", "aerial_type", "length", name="Aerial Span"),
        FieldSet("installed_by", "installation_date", "commissioned_date", name="Lifecycle"),
        FieldSet("start_structure", "end_structure", "start_location", "end_location", name="Endpoints"),
        FieldSet("start_attachment_height", "end_attachment_height", "sag", "messenger_size", name="Physical"),
        FieldSet("wind_loading", "ice_loading", name="Loading"),
        FieldSet("path", name="Geometry"),
        FieldSet("tags", name="Details"),
    )

    class Meta:
        model = AerialSpan
        fields = [
            "label",
            "status",
            "aerial_type",
            "path",
            "start_structure",
            "end_structure",
            "start_location",
            "end_location",
            "start_attachment_height",
            "end_attachment_height",
            "sag",
            "messenger_size",
            "wind_loading",
            "ice_loading",
            "length",
            "installed_by",
            "installation_date",
            "commissioned_date",
            "comments",
            "tags",
        ]
        widgets = {
            "path": PathwaysMapWidget(),
        }


class AerialSpanImportForm(PathwayPathFallbackMixin, NetBoxModelImportForm):
    status = _csv_status_field(PathwayStatusChoices)
    start_structure = _csv_structure_field("Starting")
    end_structure = _csv_structure_field("Ending")
    start_location = _csv_location_field("Starting")
    end_location = _csv_location_field("Ending")
    tenant = _csv_tenant_field("Owner tenant name")
    installed_by = _csv_tenant_field("Installer tenant name")

    path = ForgivingGeometryField(
        required=False,
        srid=get_srid(),
        geom_type="LINESTRING",
        help_text=_IMPORT_GEOMETRY_HELP,
    )

    class Meta:
        model = AerialSpan
        fields = [
            "label",
            "status",
            "aerial_type",
            "start_structure",
            "end_structure",
            "start_location",
            "end_location",
            "start_attachment_height",
            "end_attachment_height",
            "sag",
            "messenger_size",
            "wind_loading",
            "ice_loading",
            "length",
            "tenant",
            "installed_by",
            "installation_date",
            "commissioned_date",
            "path",
            "comments",
        ]


class AerialSpanBulkEditForm(NetBoxModelBulkEditForm):
    status = forms.ChoiceField(choices=PathwayStatusChoices, required=False)
    aerial_type = forms.ChoiceField(choices=AerialTypeChoices, required=False)
    messenger_size = forms.CharField(max_length=50, required=False)
    installed_by = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True)
    commissioned_date = forms.DateField(required=False)

    model = AerialSpan
    fieldsets = (
        FieldSet("status", "aerial_type", "messenger_size", name="Aerial Span"),
        FieldSet("installed_by", "commissioned_date", name="Lifecycle"),
    )
    nullable_fields = ("messenger_size", "wind_loading", "ice_loading", "installed_by", "commissioned_date")


# --- Direct Buried ---


class DirectBuriedBulkEditForm(NetBoxModelBulkEditForm):
    status = forms.ChoiceField(choices=PathwayStatusChoices, required=False)
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True)
    warning_tape = forms.NullBooleanField(required=False)
    tracer_wire = forms.NullBooleanField(required=False)
    armor_type = forms.CharField(max_length=100, required=False)
    installed_by = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True)
    commissioned_date = forms.DateField(required=False)

    model = DirectBuried
    fieldsets = (
        FieldSet("status", "tenant", "warning_tape", "tracer_wire", "armor_type", name="Direct Buried"),
        FieldSet("installed_by", "commissioned_date", name="Lifecycle"),
    )
    nullable_fields = ("tenant", "armor_type", "installed_by", "commissioned_date")


class DirectBuriedForm(PathwayEndpointFormMixin, NetBoxModelForm):
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

    installed_by = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
        label="Installed by",
    )

    fieldsets = (
        FieldSet("label", "status", "length", name="Direct Buried"),
        FieldSet("installed_by", "installation_date", "commissioned_date", name="Lifecycle"),
        FieldSet("start_structure", "end_structure", "start_location", "end_location", name="Endpoints"),
        FieldSet("burial_depth", "warning_tape", "tracer_wire", "armor_type", name="Physical"),
        FieldSet("path", name="Geometry"),
        FieldSet("tags", name="Details"),
    )

    class Meta:
        model = DirectBuried
        fields = [
            "label",
            "status",
            "path",
            "start_structure",
            "end_structure",
            "start_location",
            "end_location",
            "burial_depth",
            "warning_tape",
            "tracer_wire",
            "armor_type",
            "length",
            "installed_by",
            "installation_date",
            "commissioned_date",
            "comments",
            "tags",
        ]
        widgets = {
            "path": PathwaysMapWidget(),
        }


class DirectBuriedImportForm(PathwayPathFallbackMixin, NetBoxModelImportForm):
    status = _csv_status_field(PathwayStatusChoices)
    start_structure = _csv_structure_field("Starting")
    end_structure = _csv_structure_field("Ending")
    start_location = _csv_location_field("Starting")
    end_location = _csv_location_field("Ending")
    tenant = _csv_tenant_field("Owner tenant name")
    installed_by = _csv_tenant_field("Installer tenant name")
    path = ForgivingGeometryField(
        required=False,
        srid=get_srid(),
        geom_type="LINESTRING",
        help_text=_IMPORT_GEOMETRY_HELP,
    )

    class Meta:
        model = DirectBuried
        fields = [
            "label",
            "status",
            "start_structure",
            "end_structure",
            "start_location",
            "end_location",
            "burial_depth",
            "warning_tape",
            "tracer_wire",
            "armor_type",
            "length",
            "tenant",
            "installed_by",
            "installation_date",
            "commissioned_date",
            "path",
            "comments",
        ]


# --- Innerduct ---


class InnerductBulkEditForm(NetBoxModelBulkEditForm):
    parent_conduit = DynamicModelChoiceField(
        queryset=Conduit.objects.all(),
        required=False,
        selector=True,
    )
    status = forms.ChoiceField(choices=PathwayStatusChoices, required=False)
    color = ColorField(required=False)
    size = forms.CharField(max_length=50, required=False)
    installed_by = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True)
    commissioned_date = forms.DateField(required=False)

    model = Innerduct
    fieldsets = (
        FieldSet("status", "parent_conduit", "size", "color", name="Innerduct"),
        FieldSet("installed_by", "commissioned_date", name="Lifecycle"),
    )
    nullable_fields = ("color", "installed_by", "commissioned_date")


class InnerductForm(PathwayEndpointFormMixin, NetBoxModelForm):
    parent_conduit = DynamicModelChoiceField(
        queryset=Conduit.objects.all(),
        selector=True,
        quick_add=True,
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

    installed_by = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
        label="Installed by",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        parent = _resolve_initial_parent(self, "parent_conduit")
        if parent:
            _prefill_initial_from_parent(
                self,
                parent,
                ["start_structure", "end_structure", "start_location", "end_location"],
            )

    fieldsets = (
        FieldSet("label", "status", "parent_conduit", "size", "color", "position", name="Innerduct"),
        FieldSet("installed_by", "installation_date", "commissioned_date", name="Lifecycle"),
        FieldSet("start_structure", "end_structure", "start_location", "end_location", name="Endpoints"),
        FieldSet("length", name="Physical"),
        FieldSet("path", name="Geometry"),
        FieldSet("tags", name="Details"),
    )

    class Meta:
        model = Innerduct
        fields = [
            "label",
            "status",
            "parent_conduit",
            "size",
            "color",
            "position",
            "path",
            "start_structure",
            "end_structure",
            "start_location",
            "end_location",
            "length",
            "installed_by",
            "installation_date",
            "commissioned_date",
            "comments",
            "tags",
        ]
        widgets = {
            "path": PathwaysMapWidget(),
        }


class InnerductImportForm(PathwayPathFallbackMixin, NetBoxModelImportForm):
    status = _csv_status_field(PathwayStatusChoices)
    parent_conduit = CSVModelChoiceField(
        queryset=Conduit.objects.all(),
        help_text="Parent conduit ID (numeric)",
    )
    start_structure = _csv_structure_field("Starting")
    end_structure = _csv_structure_field("Ending")
    start_location = _csv_location_field("Starting")
    end_location = _csv_location_field("Ending")
    tenant = _csv_tenant_field("Owner tenant name")
    installed_by = _csv_tenant_field("Installer tenant name")
    color = forms.CharField(
        required=False,
        max_length=16,
        help_text='Color name (e.g. "Blue") or hex code (e.g. "2196f3")',
    )
    path = ForgivingGeometryField(
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

    class Meta:
        model = Innerduct
        fields = [
            "label",
            "status",
            "parent_conduit",
            "size",
            "color",
            "position",
            "start_structure",
            "end_structure",
            "start_location",
            "end_location",
            "length",
            "tenant",
            "installed_by",
            "installation_date",
            "commissioned_date",
            "path",
            "comments",
        ]


# --- Conduit Bank ---


class ConduitBankForm(PathwayEndpointFormMixin, NetBoxModelForm):
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
    tenant = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True, quick_add=True)
    installed_by = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
        label="Installed by",
    )

    fieldsets = (
        FieldSet("label", "status", "tenant", name="Conduit Bank"),
        FieldSet("installed_by", "installation_date", "commissioned_date", name="Lifecycle"),
        FieldSet("start_structure", "start_face", "end_structure", "end_face", name="Endpoints"),
        FieldSet("configuration", "total_conduits", "height", "width", "encasement_type", name="Configuration"),
        FieldSet("path", "length", "tags", name="Details"),
    )

    class Meta:
        model = ConduitBank
        fields = [
            "label",
            "status",
            "tenant",
            "installed_by",
            "start_structure",
            "start_face",
            "end_structure",
            "end_face",
            "configuration",
            "total_conduits",
            "height",
            "width",
            "encasement_type",
            "path",
            "length",
            "installation_date",
            "commissioned_date",
            "comments",
            "tags",
        ]
        widgets = {
            "path": PathwaysMapWidget(),
        }


class ConduitBankImportForm(PathwayPathFallbackMixin, NetBoxModelImportForm):
    status = _csv_status_field(PathwayStatusChoices)
    start_structure = _csv_structure_field("Start")
    end_structure = _csv_structure_field("End")
    start_location = _csv_location_field("Start")
    end_location = _csv_location_field("End")
    tenant = _csv_tenant_field("Owner tenant name")
    installed_by = _csv_tenant_field("Installer tenant name")

    path = ForgivingGeometryField(
        required=False,
        srid=get_srid(),
        geom_type="LINESTRING",
        help_text=_IMPORT_GEOMETRY_HELP,
    )

    class Meta:
        model = ConduitBank
        fields = [
            "label",
            "status",
            "start_structure",
            "start_face",
            "end_structure",
            "end_face",
            "start_location",
            "end_location",
            "configuration",
            "total_conduits",
            "height",
            "width",
            "encasement_type",
            "length",
            "tenant",
            "installed_by",
            "installation_date",
            "commissioned_date",
            "path",
            "comments",
        ]


class ConduitBankBulkEditForm(NetBoxModelBulkEditForm):
    status = forms.ChoiceField(choices=PathwayStatusChoices, required=False)
    start_face = forms.ChoiceField(choices=BankFaceChoices, required=False)
    end_face = forms.ChoiceField(choices=BankFaceChoices, required=False)
    configuration = forms.ChoiceField(choices=ConduitBankConfigChoices, required=False)
    encasement_type = forms.ChoiceField(choices=EncasementTypeChoices, required=False)
    height = forms.IntegerField(required=False, min_value=1)
    width = forms.IntegerField(required=False, min_value=1)
    installed_by = DynamicModelChoiceField(queryset=Tenant.objects.all(), required=False, selector=True)
    commissioned_date = forms.DateField(required=False)

    model = ConduitBank
    fieldsets = (
        FieldSet("status", "start_face", "end_face"),
        FieldSet("configuration", "encasement_type"),
        FieldSet("height", "width", name="Dimensions"),
        FieldSet("installed_by", "commissioned_date", name="Lifecycle"),
    )
    nullable_fields = (
        "start_face",
        "end_face",
        "encasement_type",
        "height",
        "width",
        "installed_by",
        "commissioned_date",
    )


# --- Conduit Junction ---


class ConduitJunctionForm(NetBoxModelForm):
    trunk_conduit = DynamicModelChoiceField(
        queryset=Conduit.objects.all(),
        selector=True,
        quick_add=True,
    )
    branch_conduit = DynamicModelChoiceField(
        queryset=Conduit.objects.all(),
        selector=True,
        quick_add=True,
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
        queryset=Conduit.objects.all(),
        help_text="Trunk conduit ID (numeric)",
    )
    branch_conduit = CSVModelChoiceField(
        queryset=Conduit.objects.all(),
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

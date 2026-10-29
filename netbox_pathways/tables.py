import django_tables2 as tables
from dcim.models import Cable
from netbox.tables import NetBoxTable, columns

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
from .pathway_types import TYPE_SPECIFIC_FIELDS_ORDERED

_LINKED_RECORD = '<a href="{{ record.get_absolute_url }}">{{ record }}</a>'

_MAP_BUTTON = (
    "<a href=\"{% url 'plugins:netbox_pathways:map' %}?select={{ record.map_select_id }}\" "
    'class="btn btn-sm btn-primary me-1" title="Show on Map">'
    '<i class="mdi mdi-map-marker-radius"></i></a>'
)

_TENANT_COLUMN = """
{% if record.tenant %}
    <a href="{{ record.tenant.get_absolute_url }}" title="{{ record.tenant.description }}">{{ record.tenant }}</a>
{% elif record.effective_tenant %}
    <a href="{{ record.effective_tenant.get_absolute_url }}" title="Inherited from the parent pathway">{{ record.effective_tenant }}</a>*
{% else %}
    &mdash;
{% endif %}
"""


class StructureTable(NetBoxTable):
    name = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    site = tables.Column(linkify=True)
    location = tables.Column(linkify=True)
    structure_type = columns.ChoiceFieldColumn()
    tenant = tables.Column(linkify=True)
    installed_by = tables.Column(linkify=True, verbose_name="Installed by")
    actions = columns.ActionsColumn(actions=("edit", "delete"), extra_buttons=_MAP_BUTTON)

    class Meta(NetBoxTable.Meta):
        model = Structure
        fields = (
            "pk",
            "id",
            "name",
            "status",
            "structure_type",
            "site",
            "location",
            "height",
            "width",
            "length",
            "depth",
            "elevation",
            "installation_date",
            "commissioned_date",
            "tenant",
            "installed_by",
            "actions",
        )
        default_columns = ("name", "status", "structure_type", "site", "tenant")


class PathwayTable(NetBoxTable):
    """Every pathway type in one table.

    Carries the columns of every type; a column whose field does not apply
    to a row's type is simply blank for that row.
    """

    pathway = tables.TemplateColumn(
        template_code=_LINKED_RECORD,
        verbose_name="Pathway",
        order_by="pk",
    )
    status = columns.ChoiceFieldColumn()
    pathway_type = columns.ChoiceFieldColumn()
    parent = tables.Column(linkify=True)
    start_structure = tables.Column(linkify=True)
    end_structure = tables.Column(linkify=True)
    start_location = tables.Column(linkify=True)
    end_location = tables.Column(linkify=True)
    tenant = tables.TemplateColumn(
        template_code=_TENANT_COLUMN,
        verbose_name="Tenant",
        order_by="tenant",
    )
    installed_by = tables.Column(linkify=True, verbose_name="Installed by")
    geo_length = tables.Column(verbose_name="Geo length (m)", order_by="_geo_length")
    cables_routed = tables.Column(verbose_name="Cables", orderable=True)
    in_use = columns.BooleanColumn(verbose_name="In Use", orderable=True)
    # Type-specific columns
    start_face = columns.ChoiceFieldColumn()
    end_face = columns.ChoiceFieldColumn()
    configuration = columns.ChoiceFieldColumn()
    encasement_type = columns.ChoiceFieldColumn()
    material = columns.ChoiceFieldColumn()
    start_junction = tables.Column(linkify=True)
    end_junction = tables.Column(linkify=True)
    aerial_type = columns.ChoiceFieldColumn()
    warning_tape = columns.BooleanColumn()
    tracer_wire = columns.BooleanColumn()
    color = columns.ColorColumn()
    actions = columns.ActionsColumn(actions=("edit", "delete"), extra_buttons=_MAP_BUTTON)

    class Meta(NetBoxTable.Meta):
        model = Pathway
        fields = (
            "pk",
            "id",
            "pathway",
            "label",
            "status",
            "pathway_type",
            "parent",
            "position",
            "start_structure",
            "end_structure",
            "start_location",
            "end_location",
            "tenant",
            "installed_by",
            "length",
            "geo_length",
            "cables_routed",
            "in_use",
            "installation_date",
            "commissioned_date",
            # "position" is shown next to "parent" above.
            *(name for name in TYPE_SPECIFIC_FIELDS_ORDERED if name != "position"),
            "actions",
        )
        default_columns = (
            "pathway",
            "status",
            "pathway_type",
            "parent",
            "start_structure",
            "end_structure",
            "in_use",
            "cables_routed",
        )


class ConduitJunctionTable(NetBoxTable):
    junction = tables.TemplateColumn(
        template_code=_LINKED_RECORD,
        verbose_name="Junction",
        order_by="pk",
    )
    trunk_conduit = tables.Column(linkify=True)
    branch_conduit = tables.Column(linkify=True)
    towards_structure = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = ConduitJunction
        fields = (
            "pk",
            "id",
            "junction",
            "label",
            "trunk_conduit",
            "branch_conduit",
            "towards_structure",
            "position_on_trunk",
            "actions",
        )
        default_columns = (
            "junction",
            "trunk_conduit",
            "branch_conduit",
            "towards_structure",
        )


class CableSegmentTable(NetBoxTable):
    cable = tables.Column(linkify=True)
    pathway = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = CableSegment
        fields = (
            "pk",
            "id",
            "cable",
            "pathway",
            "sequence",
            "actions",
        )
        default_columns = ("cable", "pathway", "sequence")


class PullSheetCableTable(NetBoxTable):
    label = tables.Column(linkify=True)
    segment_count = tables.Column(
        verbose_name="Segments",
        orderable=True,
    )
    pull_sheet = tables.TemplateColumn(
        template_code="<a href=\"{% url 'plugins:netbox_pathways:pullsheet_detail' cable_pk=record.pk %}\" "
        'class="btn btn-sm btn-primary">View Pull Sheet</a>',
        verbose_name="Pull Sheet",
        orderable=False,
    )

    class Meta(NetBoxTable.Meta):
        model = Cable
        fields = ("pk", "id", "label", "type", "status", "length", "segment_count", "pull_sheet")
        default_columns = ("label", "type", "status", "length", "segment_count", "pull_sheet")


class SiteGeometryTable(NetBoxTable):
    site = tables.Column(linkify=True)
    structure = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = SiteGeometry
        fields = ("pk", "id", "site", "structure", "actions")
        default_columns = ("site", "structure")


class PathwayLocationTable(NetBoxTable):
    pathway = tables.Column(linkify=True)
    site = tables.Column(linkify=True)
    location = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = PathwayLocation
        fields = (
            "pk",
            "id",
            "pathway",
            "site",
            "location",
            "sequence",
            "actions",
        )
        default_columns = ("pathway", "site", "location", "sequence")


class CircuitGeometryTable(NetBoxTable):
    circuit = tables.Column(linkify=True)
    provider_reference = tables.Column()
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = CircuitGeometry
        fields = ("pk", "id", "circuit", "provider_reference", "actions")
        default_columns = ("circuit", "provider_reference")


class PlannedRouteTable(NetBoxTable):
    name = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    start_structure = tables.Column(linkify=True)
    end_structure = tables.Column(linkify=True)
    tenant = tables.Column(linkify=True)
    cable = tables.Column(linkify=True)
    hop_count = tables.Column(verbose_name="Hops", accessor="hop_count", orderable=False)

    class Meta(NetBoxTable.Meta):
        model = PlannedRoute
        fields = (
            "pk",
            "name",
            "status",
            "start_structure",
            "end_structure",
            "tenant",
            "cable",
            "hop_count",
            "created",
            "actions",
        )
        default_columns = (
            "name",
            "status",
            "start_structure",
            "end_structure",
            "hop_count",
        )

import django_tables2 as tables
from dcim.models import Cable
from netbox.tables import NetBoxTable, columns

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

_LINKED_RECORD = '<a href="{{ record.get_absolute_url }}">{{ record }}</a>'

_MAP_BUTTON = (
    '<a href="{% url \'plugins:netbox_pathways:map\' %}?select='
    '{% if record.pathway_type %}{{ record.pathway_type }}{% else %}structure{% endif %}'
    '-{{ record.pk }}" class="btn btn-sm btn-primary me-1" title="Show on Map">'
    '<i class="mdi mdi-map-marker-radius"></i></a>'
)


class StructureTable(NetBoxTable):
    name = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    site = tables.Column(linkify=True)
    structure_type = columns.ChoiceFieldColumn()
    tenant = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'), extra_buttons=_MAP_BUTTON)

    class Meta(NetBoxTable.Meta):
        model = Structure
        fields = (
            'pk', 'id', 'name', 'status', 'structure_type', 'site',
            'height', 'width', 'length', 'depth', 'elevation',
            'installation_date', 'tenant', 'actions',
        )
        default_columns = ('name', 'status', 'structure_type', 'site', 'tenant')


class PathwayTable(NetBoxTable):
    pathway = tables.TemplateColumn(
        template_code=_LINKED_RECORD, verbose_name='Pathway', order_by='pk',
    )
    pathway_type = columns.ChoiceFieldColumn()
    start_structure = tables.Column(linkify=True)
    end_structure = tables.Column(linkify=True)
    start_location = tables.Column(linkify=True)
    end_location = tables.Column(linkify=True)
    tenant = tables.Column(linkify=True)
    cables_routed = tables.Column(verbose_name='Cables', orderable=True)
    in_use = columns.BooleanColumn(verbose_name='In Use', orderable=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'), extra_buttons=_MAP_BUTTON)

    class Meta(NetBoxTable.Meta):
        model = Pathway
        fields = (
            'pk', 'id', 'pathway', 'label', 'pathway_type',
            'start_structure', 'end_structure',
            'start_location', 'end_location', 'tenant', 'length',
            'cables_routed', 'in_use', 'installation_date', 'actions',
        )
        default_columns = (
            'pathway', 'pathway_type', 'start_structure', 'end_structure',
            'in_use', 'cables_routed',
        )


class ConduitTable(NetBoxTable):
    conduit = tables.TemplateColumn(
        template_code=_LINKED_RECORD, verbose_name='Conduit', order_by='pk',
    )
    material = columns.ChoiceFieldColumn()
    start_structure = tables.Column(linkify=True)
    end_structure = tables.Column(linkify=True)
    start_location = tables.Column(linkify=True)
    end_location = tables.Column(linkify=True)
    conduit_bank = tables.Column(linkify=True)
    cables_routed = tables.Column(verbose_name='Cables', orderable=True)
    in_use = columns.BooleanColumn(verbose_name='In Use', orderable=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'), extra_buttons=_MAP_BUTTON)

    class Meta(NetBoxTable.Meta):
        model = Conduit
        fields = (
            'pk', 'id', 'conduit', 'label', 'material',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            'conduit_bank', 'bank_position',
            'length', 'cables_routed', 'in_use', 'installation_date', 'actions',
        )
        default_columns = (
            'conduit', 'material', 'start_structure', 'end_structure',
            'conduit_bank', 'in_use', 'cables_routed',
        )


class AerialSpanTable(NetBoxTable):
    aerial_span = tables.TemplateColumn(
        template_code=_LINKED_RECORD, verbose_name='Aerial Span', order_by='pk',
    )
    aerial_type = columns.ChoiceFieldColumn()
    start_structure = tables.Column(linkify=True)
    end_structure = tables.Column(linkify=True)
    start_location = tables.Column(linkify=True)
    end_location = tables.Column(linkify=True)
    cables_routed = tables.Column(verbose_name='Cables', orderable=True)
    in_use = columns.BooleanColumn(verbose_name='In Use', orderable=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'), extra_buttons=_MAP_BUTTON)

    class Meta(NetBoxTable.Meta):
        model = AerialSpan
        fields = (
            'pk', 'id', 'aerial_span', 'label', 'aerial_type',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            'attachment_height', 'length',
            'cables_routed', 'in_use', 'installation_date', 'actions',
        )
        default_columns = (
            'aerial_span', 'aerial_type', 'start_structure', 'end_structure',
            'in_use', 'cables_routed',
        )


class DirectBuriedTable(NetBoxTable):
    direct_buried = tables.TemplateColumn(
        template_code=_LINKED_RECORD, verbose_name='Direct Buried', order_by='pk',
    )
    start_structure = tables.Column(linkify=True)
    end_structure = tables.Column(linkify=True)
    start_location = tables.Column(linkify=True)
    end_location = tables.Column(linkify=True)
    cables_routed = tables.Column(verbose_name='Cables', orderable=True)
    in_use = columns.BooleanColumn(verbose_name='In Use', orderable=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'), extra_buttons=_MAP_BUTTON)

    class Meta(NetBoxTable.Meta):
        model = DirectBuried
        fields = (
            'pk', 'id', 'direct_buried', 'label',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            'burial_depth', 'warning_tape', 'tracer_wire',
            'length', 'cables_routed', 'in_use', 'installation_date', 'actions',
        )
        default_columns = (
            'direct_buried', 'start_structure', 'end_structure', 'burial_depth',
            'in_use', 'cables_routed',
        )


class InnerductTable(NetBoxTable):
    innerduct = tables.TemplateColumn(
        template_code=_LINKED_RECORD, verbose_name='Innerduct', order_by='pk',
    )
    parent_conduit = tables.Column(linkify=True)
    cables_routed = tables.Column(verbose_name='Cables', orderable=True)
    in_use = columns.BooleanColumn(verbose_name='In Use', orderable=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = Innerduct
        fields = (
            'pk', 'id', 'innerduct', 'label', 'parent_conduit',
            'size', 'color', 'position',
            'cables_routed', 'in_use', 'installation_date', 'actions',
        )
        default_columns = ('innerduct', 'parent_conduit', 'size', 'color', 'in_use', 'cables_routed')


class ConduitBankTable(NetBoxTable):
    conduit_bank = tables.TemplateColumn(
        template_code=_LINKED_RECORD, verbose_name='Conduit Bank', order_by='pk',
    )
    start_structure = tables.Column(linkify=True)
    end_structure = tables.Column(linkify=True)
    start_face = columns.ChoiceFieldColumn()
    end_face = columns.ChoiceFieldColumn()
    tenant = tables.Column(linkify=True)
    configuration = columns.ChoiceFieldColumn()
    encasement_type = columns.ChoiceFieldColumn()
    conduit_count = tables.Column(
        verbose_name='Conduits',
        orderable=True,
    )
    actions = columns.ActionsColumn(actions=('edit', 'delete'), extra_buttons=_MAP_BUTTON)

    class Meta(NetBoxTable.Meta):
        model = ConduitBank
        fields = (
            'pk', 'id', 'conduit_bank', 'label', 'start_structure', 'end_structure',
            'start_face', 'end_face', 'tenant',
            'configuration', 'total_conduits', 'conduit_count',
            'encasement_type', 'length', 'installation_date', 'actions',
        )
        default_columns = (
            'conduit_bank', 'start_structure', 'end_structure',
            'configuration', 'conduit_count', 'length',
        )


class ConduitJunctionTable(NetBoxTable):
    junction = tables.TemplateColumn(
        template_code=_LINKED_RECORD, verbose_name='Junction', order_by='pk',
    )
    trunk_conduit = tables.Column(linkify=True)
    branch_conduit = tables.Column(linkify=True)
    towards_structure = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = ConduitJunction
        fields = (
            'pk', 'id', 'junction', 'label', 'trunk_conduit', 'branch_conduit',
            'towards_structure', 'position_on_trunk', 'actions',
        )
        default_columns = (
            'junction', 'trunk_conduit', 'branch_conduit', 'towards_structure',
        )


class CableSegmentTable(NetBoxTable):
    cable = tables.Column(linkify=True)
    pathway = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = CableSegment
        fields = (
            'pk', 'id', 'cable', 'pathway',
            'sequence', 'actions',
        )
        default_columns = ('cable', 'pathway', 'sequence')


class PullSheetCableTable(NetBoxTable):
    label = tables.Column(linkify=True)
    segment_count = tables.Column(
        verbose_name='Segments',
        orderable=True,
    )
    pull_sheet = tables.TemplateColumn(
        template_code='<a href="{% url \'plugins:netbox_pathways:pullsheet_detail\' cable_pk=record.pk %}" '
                      'class="btn btn-sm btn-primary">View Pull Sheet</a>',
        verbose_name='Pull Sheet',
        orderable=False,
    )

    class Meta(NetBoxTable.Meta):
        model = Cable
        fields = ('pk', 'id', 'label', 'type', 'status', 'length', 'segment_count', 'pull_sheet')
        default_columns = ('label', 'type', 'status', 'length', 'segment_count', 'pull_sheet')


class SiteGeometryTable(NetBoxTable):
    site = tables.Column(linkify=True)
    structure = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = SiteGeometry
        fields = ('pk', 'id', 'site', 'structure', 'actions')
        default_columns = ('site', 'structure')


class PathwayLocationTable(NetBoxTable):
    pathway = tables.Column(linkify=True)
    site = tables.Column(linkify=True)
    location = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = PathwayLocation
        fields = (
            'pk', 'id', 'pathway', 'site', 'location', 'sequence', 'actions',
        )
        default_columns = ('pathway', 'site', 'location', 'sequence')


class CircuitGeometryTable(NetBoxTable):
    circuit = tables.Column(linkify=True)
    provider_reference = tables.Column()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = CircuitGeometry
        fields = ('pk', 'id', 'circuit', 'provider_reference', 'actions')
        default_columns = ('circuit', 'provider_reference')


class PlannedRouteTable(NetBoxTable):
    name = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    start_structure = tables.Column(linkify=True)
    end_structure = tables.Column(linkify=True)
    tenant = tables.Column(linkify=True)
    cable = tables.Column(linkify=True)
    hop_count = tables.Column(verbose_name='Hops', accessor='hop_count', orderable=False)

    class Meta(NetBoxTable.Meta):
        model = PlannedRoute
        fields = (
            'pk', 'name', 'status', 'start_structure', 'end_structure',
            'tenant', 'cable', 'hop_count', 'created', 'actions',
        )
        default_columns = (
            'name', 'status', 'start_structure', 'end_structure', 'hop_count',
        )

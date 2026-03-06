import django_tables2 as tables
from dcim.models import Cable
from netbox.tables import NetBoxTable, columns

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


class StructureTable(NetBoxTable):
    name = tables.Column(linkify=True)
    site = tables.Column(linkify=True)
    structure_type = columns.ChoiceFieldColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = Structure
        fields = (
            'pk', 'id', 'name', 'structure_type', 'site',
            'elevation', 'installation_date', 'owner', 'actions',
        )
        default_columns = ('name', 'structure_type', 'site', 'owner')


class PathwayTable(NetBoxTable):
    name = tables.Column(linkify=True)
    pathway_type = columns.ChoiceFieldColumn()
    start_structure = tables.Column(linkify=True)
    end_structure = tables.Column(linkify=True)
    start_location = tables.Column(linkify=True)
    end_location = tables.Column(linkify=True)
    cables_routed = tables.Column(verbose_name='Cables', orderable=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = Pathway
        fields = (
            'pk', 'id', 'name', 'pathway_type',
            'start_structure', 'end_structure',
            'start_location', 'end_location', 'length',
            'cables_routed', 'installation_date', 'actions',
        )
        default_columns = (
            'name', 'pathway_type', 'start_structure', 'end_structure', 'cables_routed',
        )


class ConduitTable(NetBoxTable):
    name = tables.Column(linkify=True)
    material = columns.ChoiceFieldColumn()
    start_structure = tables.Column(linkify=True)
    end_structure = tables.Column(linkify=True)
    start_location = tables.Column(linkify=True)
    end_location = tables.Column(linkify=True)
    conduit_bank = tables.Column(linkify=True)
    cables_routed = tables.Column(verbose_name='Cables', orderable=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = Conduit
        fields = (
            'pk', 'id', 'name', 'material',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            'conduit_bank', 'bank_position',
            'length', 'cables_routed', 'installation_date', 'actions',
        )
        default_columns = (
            'name', 'material', 'start_structure', 'end_structure',
            'conduit_bank', 'cables_routed',
        )


class AerialSpanTable(NetBoxTable):
    name = tables.Column(linkify=True)
    aerial_type = columns.ChoiceFieldColumn()
    start_structure = tables.Column(linkify=True)
    end_structure = tables.Column(linkify=True)
    start_location = tables.Column(linkify=True)
    end_location = tables.Column(linkify=True)
    cables_routed = tables.Column(verbose_name='Cables', orderable=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = AerialSpan
        fields = (
            'pk', 'id', 'name', 'aerial_type',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            'attachment_height', 'length',
            'cables_routed', 'installation_date', 'actions',
        )
        default_columns = (
            'name', 'aerial_type', 'start_structure', 'end_structure', 'cables_routed',
        )


class DirectBuriedTable(NetBoxTable):
    name = tables.Column(linkify=True)
    start_structure = tables.Column(linkify=True)
    end_structure = tables.Column(linkify=True)
    start_location = tables.Column(linkify=True)
    end_location = tables.Column(linkify=True)
    cables_routed = tables.Column(verbose_name='Cables', orderable=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = DirectBuried
        fields = (
            'pk', 'id', 'name',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            'burial_depth', 'warning_tape', 'tracer_wire',
            'length', 'cables_routed', 'installation_date', 'actions',
        )
        default_columns = (
            'name', 'start_structure', 'end_structure', 'burial_depth', 'cables_routed',
        )


class InnerductTable(NetBoxTable):
    name = tables.Column(linkify=True)
    parent_conduit = tables.Column(linkify=True)
    cables_routed = tables.Column(verbose_name='Cables', orderable=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = Innerduct
        fields = (
            'pk', 'id', 'name', 'parent_conduit',
            'size', 'color', 'position',
            'cables_routed', 'installation_date', 'actions',
        )
        default_columns = ('name', 'parent_conduit', 'size', 'color', 'cables_routed')


class ConduitBankTable(NetBoxTable):
    name = tables.Column(linkify=True)
    structure = tables.Column(linkify=True)
    configuration = columns.ChoiceFieldColumn()
    encasement_type = columns.ChoiceFieldColumn()
    conduit_count = tables.Column(
        verbose_name='Conduits',
        orderable=True,
    )
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = ConduitBank
        fields = (
            'pk', 'id', 'name', 'structure',
            'configuration', 'total_conduits', 'conduit_count',
            'encasement_type', 'installation_date', 'actions',
        )
        default_columns = (
            'name', 'structure', 'configuration', 'total_conduits', 'conduit_count',
        )


class ConduitJunctionTable(NetBoxTable):
    name = tables.Column(linkify=True)
    trunk_conduit = tables.Column(linkify=True)
    branch_conduit = tables.Column(linkify=True)
    towards_structure = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = ConduitJunction
        fields = (
            'pk', 'id', 'name', 'trunk_conduit', 'branch_conduit',
            'towards_structure', 'position_on_trunk', 'actions',
        )
        default_columns = (
            'name', 'trunk_conduit', 'branch_conduit', 'towards_structure',
        )


class CableSegmentTable(NetBoxTable):
    cable = tables.Column(linkify=True)
    pathway = tables.Column(linkify=True)
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = CableSegment
        fields = (
            'pk', 'id', 'cable', 'pathway', 'sequence',
            'slack_length', 'actions',
        )
        default_columns = ('cable', 'pathway', 'sequence', 'slack_length')


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

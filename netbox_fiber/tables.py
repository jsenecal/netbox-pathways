import django_tables2 as tables
from netbox.tables import NetBoxTable, columns
from .models import FiberStructure, FiberConduit, FiberSplice, FiberCableSegment


class FiberStructureTable(NetBoxTable):
    name = tables.Column(
        linkify=True
    )
    site = tables.Column(
        linkify=True
    )
    structure_type = columns.ChoiceFieldColumn()
    conduits_in = tables.Column(
        verbose_name='Conduits In',
        accessor='conduits_in__count',
        orderable=False
    )
    conduits_out = tables.Column(
        verbose_name='Conduits Out',
        accessor='conduits_out__count',
        orderable=False
    )
    actions = columns.ActionsColumn(
        actions=('edit', 'delete')
    )

    class Meta(NetBoxTable.Meta):
        model = FiberStructure
        fields = (
            'pk', 'id', 'name', 'structure_type', 'site', 
            'elevation', 'installation_date', 'owner',
            'conduits_in', 'conduits_out', 'actions',
        )
        default_columns = (
            'name', 'structure_type', 'site', 'conduits_in', 'conduits_out',
        )


class FiberConduitTable(NetBoxTable):
    name = tables.Column(
        linkify=True
    )
    start_structure = tables.Column(
        linkify=True
    )
    end_structure = tables.Column(
        linkify=True
    )
    conduit_type = columns.ChoiceFieldColumn()
    material = columns.ChoiceFieldColumn()
    utilization = tables.Column(
        verbose_name='Utilization %',
        accessor='utilization_percentage',
        orderable=False
    )
    cable_usage = tables.TemplateColumn(
        template_code='{{ record.cable_count }}/{{ record.max_cable_count }}',
        verbose_name='Cable Usage',
        orderable=False
    )
    actions = columns.ActionsColumn(
        actions=('edit', 'delete')
    )

    class Meta(NetBoxTable.Meta):
        model = FiberConduit
        fields = (
            'pk', 'id', 'name', 'conduit_type', 'material',
            'start_structure', 'end_structure', 'length',
            'cable_usage', 'utilization', 'installation_date', 'actions',
        )
        default_columns = (
            'name', 'conduit_type', 'start_structure', 'end_structure',
            'cable_usage', 'utilization',
        )


class FiberSpliceTable(NetBoxTable):
    name = tables.Column(
        linkify=True
    )
    structure = tables.Column(
        linkify=True
    )
    actions = columns.ActionsColumn(
        actions=('edit', 'delete')
    )

    class Meta(NetBoxTable.Meta):
        model = FiberSplice
        fields = (
            'pk', 'id', 'name', 'structure', 'enclosure_type',
            'fiber_count', 'installation_date', 'actions',
        )
        default_columns = (
            'name', 'structure', 'enclosure_type', 'fiber_count',
        )


class FiberCableSegmentTable(NetBoxTable):
    cable = tables.Column(
        linkify=True
    )
    conduit = tables.Column(
        linkify=True
    )
    actions = columns.ActionsColumn(
        actions=('edit', 'delete')
    )

    class Meta(NetBoxTable.Meta):
        model = FiberCableSegment
        fields = (
            'pk', 'id', 'cable', 'conduit', 'sequence',
            'slack_length', 'actions',
        )
        default_columns = (
            'cable', 'conduit', 'sequence', 'slack_length',
        )
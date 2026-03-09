from netbox.search import SearchIndex, register_search

from . import models


@register_search
class StructureIndex(SearchIndex):
    model = models.Structure
    fields = (
        ('name', 100),
        ('structure_type', 200),
        ('access_notes', 500),
        ('comments', 5000),
    )
    display_attrs = ('structure_type', 'site', 'tenant')


@register_search
class ConduitIndex(SearchIndex):
    model = models.Conduit
    fields = (
        ('name', 100),
        ('material', 200),
        ('bank_position', 300),
        ('comments', 5000),
    )
    display_attrs = ('material', 'start_structure', 'end_structure')


@register_search
class AerialSpanIndex(SearchIndex):
    model = models.AerialSpan
    fields = (
        ('name', 100),
        ('aerial_type', 200),
        ('messenger_size', 300),
        ('comments', 5000),
    )
    display_attrs = ('aerial_type', 'start_structure', 'end_structure')


@register_search
class DirectBuriedIndex(SearchIndex):
    model = models.DirectBuried
    fields = (
        ('name', 100),
        ('armor_type', 200),
        ('comments', 5000),
    )
    display_attrs = ('start_structure', 'end_structure')


@register_search
class InnerductIndex(SearchIndex):
    model = models.Innerduct
    fields = (
        ('name', 100),
        ('size', 200),
        ('color', 300),
        ('position', 300),
        ('comments', 5000),
    )
    display_attrs = ('parent_conduit', 'size', 'color')


@register_search
class ConduitBankIndex(SearchIndex):
    model = models.ConduitBank
    fields = (
        ('name', 100),
        ('configuration', 200),
        ('encasement_type', 300),
        ('comments', 5000),
    )
    display_attrs = ('structure', 'configuration', 'total_conduits')


@register_search
class ConduitJunctionIndex(SearchIndex):
    model = models.ConduitJunction
    fields = (
        ('name', 100),
        ('comments', 5000),
    )
    display_attrs = ('trunk_conduit', 'branch_conduit', 'towards_structure')


@register_search
class PathwayLocationIndex(SearchIndex):
    model = models.PathwayLocation
    fields = (
        ('comments', 5000),
    )
    display_attrs = ('pathway', 'site', 'location', 'sequence')


@register_search
class CableSegmentIndex(SearchIndex):
    model = models.CableSegment
    fields = (
        ('comments', 5000),
    )
    display_attrs = ('cable', 'pathway', 'sequence')


@register_search
class SiteGeometryIndex(SearchIndex):
    model = models.SiteGeometry
    fields = (
        ('comments', 5000),
    )
    display_attrs = ('site', 'structure')

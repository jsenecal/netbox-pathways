from netbox.search import SearchIndex, register_search

from . import models


@register_search
class StructureIndex(SearchIndex):
    model = models.Structure
    fields = (
        ('name', 100),
        ('owner', 200),
        ('access_notes', 500),
        ('comments', 5000),
    )
    display_attrs = ('structure_type', 'site', 'owner')


@register_search
class ConduitIndex(SearchIndex):
    model = models.Conduit
    fields = (
        ('name', 100),
        ('comments', 5000),
    )
    display_attrs = ('material', 'start_structure', 'end_structure')


@register_search
class AerialSpanIndex(SearchIndex):
    model = models.AerialSpan
    fields = (
        ('name', 100),
        ('comments', 5000),
    )
    display_attrs = ('aerial_type', 'start_structure', 'end_structure')


@register_search
class DirectBuriedIndex(SearchIndex):
    model = models.DirectBuried
    fields = (
        ('name', 100),
        ('comments', 5000),
    )
    display_attrs = ('start_structure', 'end_structure')


@register_search
class InnerductIndex(SearchIndex):
    model = models.Innerduct
    fields = (
        ('name', 100),
        ('comments', 5000),
    )
    display_attrs = ('parent_conduit', 'size', 'color')


@register_search
class ConduitBankIndex(SearchIndex):
    model = models.ConduitBank
    fields = (
        ('name', 100),
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
    display_attrs = ('trunk_conduit', 'branch_conduit')


@register_search
class CableSegmentIndex(SearchIndex):
    model = models.CableSegment
    fields = (
        ('comments', 5000),
    )
    display_attrs = ('cable', 'pathway', 'sequence')

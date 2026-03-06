from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import (
    AerialSpan,
    CableSegment,
    Conduit,
    ConduitBank,
    ConduitJunction,
    DirectBuried,
    Innerduct,
    PathwayLocation,
    Structure,
)


@admin.register(Structure)
class StructureAdmin(GISModelAdmin):
    list_display = ['name', 'structure_type', 'site', 'elevation', 'owner']
    list_filter = ['structure_type', 'site']
    search_fields = ['name', 'owner']
    ordering = ['name']


@admin.register(Conduit)
class ConduitAdmin(GISModelAdmin):
    list_display = ['name', 'material', 'start_structure', 'end_structure', 'length']
    list_filter = ['material']
    search_fields = ['name']
    ordering = ['name']


@admin.register(AerialSpan)
class AerialSpanAdmin(GISModelAdmin):
    list_display = ['name', 'aerial_type', 'start_structure', 'end_structure', 'length']
    list_filter = ['aerial_type']
    search_fields = ['name']
    ordering = ['name']


@admin.register(DirectBuried)
class DirectBuriedAdmin(GISModelAdmin):
    list_display = ['name', 'start_structure', 'end_structure', 'burial_depth', 'length']
    search_fields = ['name']
    ordering = ['name']


@admin.register(Innerduct)
class InnerductAdmin(GISModelAdmin):
    list_display = ['name', 'parent_conduit', 'size', 'color']
    search_fields = ['name']
    ordering = ['name']


@admin.register(ConduitBank)
class ConduitBankAdmin(admin.ModelAdmin):
    list_display = ['name', 'structure', 'configuration', 'total_conduits']
    list_filter = ['configuration']
    search_fields = ['name']
    ordering = ['name']


@admin.register(ConduitJunction)
class ConduitJunctionAdmin(admin.ModelAdmin):
    list_display = ['name', 'trunk_conduit', 'branch_conduit', 'position_on_trunk']
    search_fields = ['name']
    ordering = ['name']


@admin.register(PathwayLocation)
class PathwayLocationAdmin(admin.ModelAdmin):
    list_display = ['pathway', 'site', 'location', 'sequence']
    list_filter = ['site']
    search_fields = ['pathway__name']
    ordering = ['pathway', 'sequence']


@admin.register(CableSegment)
class CableSegmentAdmin(GISModelAdmin):
    list_display = ['cable', 'pathway', 'sequence', 'slack_length']
    list_filter = ['pathway']
    search_fields = ['cable__label']
    ordering = ['cable', 'sequence']

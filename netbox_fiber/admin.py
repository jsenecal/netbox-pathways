from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from .models import FiberStructure, FiberConduit, FiberSplice, FiberCableSegment


@admin.register(FiberStructure)
class FiberStructureAdmin(GISModelAdmin):
    list_display = ['name', 'structure_type', 'site', 'elevation', 'owner']
    list_filter = ['structure_type', 'site']
    search_fields = ['name', 'owner']
    ordering = ['name']


@admin.register(FiberConduit)
class FiberConduitAdmin(GISModelAdmin):
    list_display = ['name', 'conduit_type', 'start_structure', 'end_structure', 'length']
    list_filter = ['conduit_type', 'material']
    search_fields = ['name']
    ordering = ['name']


@admin.register(FiberSplice)
class FiberSpliceAdmin(admin.ModelAdmin):
    list_display = ['name', 'structure', 'enclosure_type', 'fiber_count']
    list_filter = ['enclosure_type']
    search_fields = ['name', 'structure__name']
    ordering = ['name']


@admin.register(FiberCableSegment)
class FiberCableSegmentAdmin(GISModelAdmin):
    list_display = ['cable', 'conduit', 'sequence', 'slack_length']
    list_filter = ['conduit']
    search_fields = ['cable__label']
    ordering = ['cable', 'sequence']
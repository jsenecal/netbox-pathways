import django_filters
from django.db.models import Q
from netbox.filtersets import NetBoxModelFilterSet
from dcim.models import Site
from .models import FiberStructure, FiberConduit, FiberSplice, FiberCableSegment


class FiberStructureFilterSet(NetBoxModelFilterSet):
    site_id = django_filters.ModelMultipleChoiceFilter(
        field_name='site',
        queryset=Site.objects.all(),
        label='Site (ID)',
    )
    site = django_filters.ModelMultipleChoiceFilter(
        field_name='site__name',
        queryset=Site.objects.all(),
        to_field_name='name',
        label='Site (name)',
    )
    structure_type = django_filters.MultipleChoiceFilter(
        choices=[]
    )
    owner = django_filters.CharFilter(
        lookup_expr='icontains'
    )
    
    class Meta:
        model = FiberStructure
        fields = ['id', 'name', 'structure_type', 'elevation', 'installation_date']
    
    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) |
            Q(owner__icontains=value) |
            Q(access_notes__icontains=value)
        )


class FiberConduitFilterSet(NetBoxModelFilterSet):
    start_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='start_structure',
        queryset=FiberStructure.objects.all(),
        label='Start Structure (ID)',
    )
    start_structure = django_filters.ModelMultipleChoiceFilter(
        field_name='start_structure__name',
        queryset=FiberStructure.objects.all(),
        to_field_name='name',
        label='Start Structure (name)',
    )
    end_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='end_structure',
        queryset=FiberStructure.objects.all(),
        label='End Structure (ID)',
    )
    end_structure = django_filters.ModelMultipleChoiceFilter(
        field_name='end_structure__name',
        queryset=FiberStructure.objects.all(),
        to_field_name='name',
        label='End Structure (name)',
    )
    conduit_type = django_filters.MultipleChoiceFilter(
        choices=[]
    )
    material = django_filters.MultipleChoiceFilter(
        choices=[]
    )
    
    class Meta:
        model = FiberConduit
        fields = ['id', 'name', 'conduit_type', 'material', 'length', 'installation_date']
    
    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) |
            Q(comments__icontains=value)
        )
import django_filters
from circuits.models import Circuit, Provider
from dcim.models import Cable, Location, Site
from django.db.models import Q
from netbox.filtersets import NetBoxModelFilterSet
from tenancy.models import Tenant

from .choices import (
    AerialTypeChoices,
    ConduitBankConfigChoices,
    ConduitMaterialChoices,
    EncasementTypeChoices,
    PathwayTypeChoices,
    StructureTypeChoices,
)
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
    SiteGeometry,
    Structure,
)


class StructureFilterSet(NetBoxModelFilterSet):
    site_id = django_filters.ModelMultipleChoiceFilter(
        field_name='site', queryset=Site.objects.all(), label='Site (ID)',
    )
    site = django_filters.ModelMultipleChoiceFilter(
        field_name='site__name', queryset=Site.objects.all(),
        to_field_name='name', label='Site (name)',
    )
    structure_type = django_filters.MultipleChoiceFilter(choices=StructureTypeChoices)
    tenant_id = django_filters.ModelMultipleChoiceFilter(
        field_name='tenant', queryset=Tenant.objects.all(), label='Tenant (ID)',
    )
    tenant = django_filters.ModelMultipleChoiceFilter(
        field_name='tenant__name', queryset=Tenant.objects.all(),
        to_field_name='name', label='Tenant (name)',
    )

    class Meta:
        model = Structure
        fields = ['id', 'name', 'structure_type', 'height', 'width', 'length', 'depth', 'elevation', 'installation_date']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) |
            Q(tenant__name__icontains=value) |
            Q(access_notes__icontains=value)
        )


class PathwayFilterSet(NetBoxModelFilterSet):
    pathway_type = django_filters.MultipleChoiceFilter(choices=PathwayTypeChoices)
    tenant_id = django_filters.ModelMultipleChoiceFilter(
        field_name='tenant', queryset=Tenant.objects.all(), label='Tenant (ID)',
    )
    start_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='start_structure', queryset=Structure.objects.all(),
        label='Start Structure (ID)',
    )
    end_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='end_structure', queryset=Structure.objects.all(),
        label='End Structure (ID)',
    )
    start_location_id = django_filters.ModelMultipleChoiceFilter(
        field_name='start_location', queryset=Location.objects.all(),
        label='Start Location (ID)',
    )
    end_location_id = django_filters.ModelMultipleChoiceFilter(
        field_name='end_location', queryset=Location.objects.all(),
        label='End Location (ID)',
    )

    class Meta:
        model = Pathway
        fields = ['id', 'name', 'pathway_type', 'length', 'installation_date']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(comments__icontains=value)
        )


class ConduitFilterSet(NetBoxModelFilterSet):
    material = django_filters.MultipleChoiceFilter(choices=ConduitMaterialChoices)
    start_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='start_structure', queryset=Structure.objects.all(),
        label='Start Structure (ID)',
    )
    end_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='end_structure', queryset=Structure.objects.all(),
        label='End Structure (ID)',
    )
    start_location_id = django_filters.ModelMultipleChoiceFilter(
        field_name='start_location', queryset=Location.objects.all(),
        label='Start Location (ID)',
    )
    end_location_id = django_filters.ModelMultipleChoiceFilter(
        field_name='end_location', queryset=Location.objects.all(),
        label='End Location (ID)',
    )
    conduit_bank_id = django_filters.ModelMultipleChoiceFilter(
        field_name='conduit_bank', queryset=ConduitBank.objects.all(),
        label='Conduit Bank (ID)',
    )

    class Meta:
        model = Conduit
        fields = ['id', 'name', 'material', 'length', 'installation_date']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(comments__icontains=value)
        )


class AerialSpanFilterSet(NetBoxModelFilterSet):
    aerial_type = django_filters.MultipleChoiceFilter(choices=AerialTypeChoices)
    start_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='start_structure', queryset=Structure.objects.all(),
        label='Start Structure (ID)',
    )
    end_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='end_structure', queryset=Structure.objects.all(),
        label='End Structure (ID)',
    )
    start_location_id = django_filters.ModelMultipleChoiceFilter(
        field_name='start_location', queryset=Location.objects.all(),
        label='Start Location (ID)',
    )
    end_location_id = django_filters.ModelMultipleChoiceFilter(
        field_name='end_location', queryset=Location.objects.all(),
        label='End Location (ID)',
    )

    class Meta:
        model = AerialSpan
        fields = ['id', 'name', 'aerial_type', 'length', 'installation_date']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(comments__icontains=value)
        )


class DirectBuriedFilterSet(NetBoxModelFilterSet):
    start_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='start_structure', queryset=Structure.objects.all(),
        label='Start Structure (ID)',
    )
    end_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='end_structure', queryset=Structure.objects.all(),
        label='End Structure (ID)',
    )
    start_location_id = django_filters.ModelMultipleChoiceFilter(
        field_name='start_location', queryset=Location.objects.all(),
        label='Start Location (ID)',
    )
    end_location_id = django_filters.ModelMultipleChoiceFilter(
        field_name='end_location', queryset=Location.objects.all(),
        label='End Location (ID)',
    )

    class Meta:
        model = DirectBuried
        fields = ['id', 'name', 'length', 'installation_date']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(comments__icontains=value)
        )


class InnerductFilterSet(NetBoxModelFilterSet):
    parent_conduit_id = django_filters.ModelMultipleChoiceFilter(
        field_name='parent_conduit', queryset=Conduit.objects.all(),
        label='Parent Conduit (ID)',
    )

    class Meta:
        model = Innerduct
        fields = ['id', 'name', 'size', 'color', 'installation_date']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(comments__icontains=value)
        )


class ConduitBankFilterSet(NetBoxModelFilterSet):
    structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='structure', queryset=Structure.objects.all(),
        label='Structure (ID)',
    )
    tenant_id = django_filters.ModelMultipleChoiceFilter(
        field_name='tenant', queryset=Tenant.objects.all(), label='Tenant (ID)',
    )
    configuration = django_filters.MultipleChoiceFilter(choices=ConduitBankConfigChoices)
    encasement_type = django_filters.MultipleChoiceFilter(choices=EncasementTypeChoices)

    class Meta:
        model = ConduitBank
        fields = ['id', 'name', 'configuration', 'encasement_type', 'installation_date']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(comments__icontains=value)
        )


class ConduitJunctionFilterSet(NetBoxModelFilterSet):
    trunk_conduit_id = django_filters.ModelMultipleChoiceFilter(
        field_name='trunk_conduit', queryset=Conduit.objects.all(),
        label='Trunk Conduit (ID)',
    )
    branch_conduit_id = django_filters.ModelMultipleChoiceFilter(
        field_name='branch_conduit', queryset=Conduit.objects.all(),
        label='Branch Conduit (ID)',
    )

    class Meta:
        model = ConduitJunction
        fields = ['id', 'name']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(comments__icontains=value)
        )


class CableSegmentFilterSet(NetBoxModelFilterSet):
    cable_id = django_filters.ModelMultipleChoiceFilter(
        field_name='cable', queryset=Cable.objects.all(),
        label='Cable (ID)',
    )
    pathway_id = django_filters.ModelMultipleChoiceFilter(
        field_name='pathway', queryset=Pathway.objects.all(),
        label='Pathway (ID)',
    )

    class Meta:
        model = CableSegment
        fields = ['id', 'sequence']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(comments__icontains=value))


class PathwayLocationFilterSet(NetBoxModelFilterSet):
    pathway_id = django_filters.ModelMultipleChoiceFilter(
        field_name='pathway', queryset=Pathway.objects.all(),
        label='Pathway (ID)',
    )
    site_id = django_filters.ModelMultipleChoiceFilter(
        field_name='site', queryset=Site.objects.all(),
        label='Site (ID)',
    )
    location_id = django_filters.ModelMultipleChoiceFilter(
        field_name='location', queryset=Location.objects.all(),
        label='Location (ID)',
    )

    class Meta:
        model = PathwayLocation
        fields = ['id', 'sequence']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(comments__icontains=value))


class SiteGeometryFilterSet(NetBoxModelFilterSet):
    site_id = django_filters.ModelMultipleChoiceFilter(
        field_name='site', queryset=Site.objects.all(), label='Site (ID)',
    )
    structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name='structure', queryset=Structure.objects.all(), label='Structure (ID)',
    )

    class Meta:
        model = SiteGeometry
        fields = ['id']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(site__name__icontains=value))


class CircuitGeometryFilterSet(NetBoxModelFilterSet):
    circuit_id = django_filters.ModelMultipleChoiceFilter(
        field_name='circuit', queryset=Circuit.objects.all(),
        label='Circuit (ID)',
    )
    provider_id = django_filters.ModelMultipleChoiceFilter(
        field_name='circuit__provider', queryset=Provider.objects.all(),
        label='Provider (ID)',
    )

    class Meta:
        model = CircuitGeometry
        fields = ['id']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(circuit__cid__icontains=value) |
            Q(provider_reference__icontains=value)
        )

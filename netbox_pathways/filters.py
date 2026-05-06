import django_filters
from circuits.models import Circuit, Provider
from dcim.models import Cable, Location, Site
from django.db.models import Q
from netbox.filtersets import NetBoxModelFilterSet
from tenancy.filtersets import TenancyFilterSet
from tenancy.models import Tenant
from utilities.filters import MultiValueCharFilter, MultiValueNumberFilter

from .choices import (
    AerialTypeChoices,
    BankFaceChoices,
    ConduitBankConfigChoices,
    ConduitMaterialChoices,
    EncasementTypeChoices,
    PathwayTypeChoices,
    PlannedRouteStatusChoices,
    StructureStatusChoices,
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
    PlannedRoute,
    SiteGeometry,
    Structure,
)


class StructureFilterSet(TenancyFilterSet, NetBoxModelFilterSet):
    name = MultiValueCharFilter()
    status = django_filters.MultipleChoiceFilter(
        choices=StructureStatusChoices,
        distinct=False,
        null_value=None,
    )
    structure_type = django_filters.MultipleChoiceFilter(
        choices=StructureTypeChoices,
        distinct=False,
        null_value=None,
    )
    site_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Site.objects.all(),
        distinct=False,
        label="Site (ID)",
    )
    site = django_filters.ModelMultipleChoiceFilter(
        field_name="site__slug",
        queryset=Site.objects.all(),
        to_field_name="slug",
        distinct=False,
        label="Site (slug)",
    )
    installed_by_id = django_filters.ModelMultipleChoiceFilter(
        field_name="installed_by",
        queryset=Tenant.objects.all(),
        distinct=False,
        label="Installed by (ID)",
    )
    height = MultiValueNumberFilter()
    width = MultiValueNumberFilter()
    length = MultiValueNumberFilter()
    depth = MultiValueNumberFilter()
    elevation = MultiValueNumberFilter()
    occupied = django_filters.BooleanFilter(
        method="filter_occupied",
        label="Occupied (has routed cables)",
    )
    has_pathways = django_filters.BooleanFilter(
        method="filter_has_pathways",
        label="Has connected pathways",
    )

    class Meta:
        model = Structure
        fields = ["id", "installation_date", "commissioned_date"]

    def filter_occupied(self, queryset, name, value):
        occupied_pws = CableSegment.objects.values_list("pathway_id", flat=True)
        occupied_struct_pks = set()
        for start_pk, end_pk in Pathway.objects.filter(pk__in=occupied_pws).values_list(
            "start_structure_id", "end_structure_id"
        ):
            if start_pk:
                occupied_struct_pks.add(start_pk)
            if end_pk:
                occupied_struct_pks.add(end_pk)
        if value:
            return queryset.filter(pk__in=occupied_struct_pks)
        return queryset.exclude(pk__in=occupied_struct_pks)

    def filter_has_pathways(self, queryset, name, value):
        connected = Pathway.objects.values_list(
            "start_structure_id",
            "end_structure_id",
        )
        pks = set()
        for start_pk, end_pk in connected:
            if start_pk:
                pks.add(start_pk)
            if end_pk:
                pks.add(end_pk)
        if value:
            return queryset.filter(pk__in=pks)
        return queryset.exclude(pk__in=pks)

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(tenant__name__icontains=value) | Q(access_notes__icontains=value)
        )


class PathwayFilterSet(TenancyFilterSet, NetBoxModelFilterSet):
    label = MultiValueCharFilter()
    pathway_type = django_filters.MultipleChoiceFilter(
        choices=PathwayTypeChoices,
        distinct=False,
        null_value=None,
    )
    structure_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Structure.objects.all(),
        distinct=False,
        label="Structure (ID)",
        method="filter_structure",
    )
    start_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name="start_structure",
        queryset=Structure.objects.all(),
        distinct=False,
        label="Start Structure (ID)",
    )
    end_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name="end_structure",
        queryset=Structure.objects.all(),
        distinct=False,
        label="End Structure (ID)",
    )
    start_location_id = django_filters.ModelMultipleChoiceFilter(
        field_name="start_location",
        queryset=Location.objects.all(),
        distinct=False,
        label="Start Location (ID)",
    )
    end_location_id = django_filters.ModelMultipleChoiceFilter(
        field_name="end_location",
        queryset=Location.objects.all(),
        distinct=False,
        label="End Location (ID)",
    )
    start_location = django_filters.ModelMultipleChoiceFilter(
        field_name="start_location__slug",
        queryset=Location.objects.all(),
        to_field_name="slug",
        distinct=False,
        label="Start Location (slug)",
    )
    end_location = django_filters.ModelMultipleChoiceFilter(
        field_name="end_location__slug",
        queryset=Location.objects.all(),
        to_field_name="slug",
        distinct=False,
        label="End Location (slug)",
    )
    length = MultiValueNumberFilter()
    installed_by_id = django_filters.ModelMultipleChoiceFilter(
        field_name="installed_by",
        queryset=Tenant.objects.all(),
        distinct=False,
        label="Installed by (ID)",
    )
    occupied = django_filters.BooleanFilter(
        method="filter_occupied",
        label="Occupied (has routed cables)",
    )

    class Meta:
        model = Pathway
        fields = ["id", "installation_date", "commissioned_date"]

    def filter_occupied(self, queryset, name, value):
        occupied_pws = CableSegment.objects.values_list("pathway_id", flat=True)
        if value:
            return queryset.filter(pk__in=occupied_pws)
        return queryset.exclude(pk__in=occupied_pws)

    def filter_structure(self, queryset, name, value):
        """Filter to pathways connected to a structure at either end.

        Uses Pathway.map_queryset() to exclude innerducts and bank-member
        conduits — same visibility rules as the map.
        """
        if not value:
            return queryset
        from .models import Pathway

        return Pathway.map_queryset(queryset).filter(
            Q(start_structure__in=value) | Q(end_structure__in=value),
        )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(label__icontains=value) | Q(comments__icontains=value))


class ConduitFilterSet(NetBoxModelFilterSet):
    label = MultiValueCharFilter()
    material = django_filters.MultipleChoiceFilter(
        choices=ConduitMaterialChoices,
        distinct=False,
        null_value=None,
    )
    start_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name="start_structure",
        queryset=Structure.objects.all(),
        distinct=False,
        label="Start Structure (ID)",
    )
    end_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name="end_structure",
        queryset=Structure.objects.all(),
        distinct=False,
        label="End Structure (ID)",
    )
    start_location_id = django_filters.ModelMultipleChoiceFilter(
        field_name="start_location",
        queryset=Location.objects.all(),
        distinct=False,
        label="Start Location (ID)",
    )
    end_location_id = django_filters.ModelMultipleChoiceFilter(
        field_name="end_location",
        queryset=Location.objects.all(),
        distinct=False,
        label="End Location (ID)",
    )
    conduit_bank_id = django_filters.ModelMultipleChoiceFilter(
        field_name="conduit_bank",
        queryset=ConduitBank.objects.all(),
        distinct=False,
        label="Conduit Bank (ID)",
    )
    inner_diameter = MultiValueNumberFilter()
    outer_diameter = MultiValueNumberFilter()
    depth = MultiValueNumberFilter()
    length = MultiValueNumberFilter()

    class Meta:
        model = Conduit
        fields = ["id", "installation_date", "commissioned_date"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(label__icontains=value) | Q(comments__icontains=value))


class AerialSpanFilterSet(NetBoxModelFilterSet):
    label = MultiValueCharFilter()
    aerial_type = django_filters.MultipleChoiceFilter(
        choices=AerialTypeChoices,
        distinct=False,
        null_value=None,
    )
    start_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name="start_structure",
        queryset=Structure.objects.all(),
        distinct=False,
        label="Start Structure (ID)",
    )
    end_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name="end_structure",
        queryset=Structure.objects.all(),
        distinct=False,
        label="End Structure (ID)",
    )
    start_location_id = django_filters.ModelMultipleChoiceFilter(
        field_name="start_location",
        queryset=Location.objects.all(),
        distinct=False,
        label="Start Location (ID)",
    )
    end_location_id = django_filters.ModelMultipleChoiceFilter(
        field_name="end_location",
        queryset=Location.objects.all(),
        distinct=False,
        label="End Location (ID)",
    )
    attachment_height = MultiValueNumberFilter()
    sag = MultiValueNumberFilter()
    length = MultiValueNumberFilter()
    messenger_size = MultiValueCharFilter()
    wind_loading = MultiValueCharFilter()
    ice_loading = MultiValueCharFilter()

    class Meta:
        model = AerialSpan
        fields = ["id", "installation_date", "commissioned_date"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(label__icontains=value) | Q(comments__icontains=value))


class DirectBuriedFilterSet(NetBoxModelFilterSet):
    label = MultiValueCharFilter()
    start_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name="start_structure",
        queryset=Structure.objects.all(),
        distinct=False,
        label="Start Structure (ID)",
    )
    end_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name="end_structure",
        queryset=Structure.objects.all(),
        distinct=False,
        label="End Structure (ID)",
    )
    start_location_id = django_filters.ModelMultipleChoiceFilter(
        field_name="start_location",
        queryset=Location.objects.all(),
        distinct=False,
        label="Start Location (ID)",
    )
    end_location_id = django_filters.ModelMultipleChoiceFilter(
        field_name="end_location",
        queryset=Location.objects.all(),
        distinct=False,
        label="End Location (ID)",
    )
    burial_depth = MultiValueNumberFilter()
    warning_tape = django_filters.BooleanFilter()
    tracer_wire = django_filters.BooleanFilter()
    armor_type = MultiValueCharFilter()
    length = MultiValueNumberFilter()

    class Meta:
        model = DirectBuried
        fields = ["id", "installation_date", "commissioned_date"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(label__icontains=value) | Q(comments__icontains=value))


class InnerductFilterSet(NetBoxModelFilterSet):
    label = MultiValueCharFilter()
    parent_conduit_id = django_filters.ModelMultipleChoiceFilter(
        field_name="parent_conduit",
        queryset=Conduit.objects.all(),
        distinct=False,
        label="Parent Conduit (ID)",
    )
    size = MultiValueCharFilter()
    color = MultiValueCharFilter()
    position = MultiValueCharFilter()

    class Meta:
        model = Innerduct
        fields = ["id", "installation_date", "commissioned_date"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(label__icontains=value) | Q(comments__icontains=value))


class ConduitBankFilterSet(TenancyFilterSet, NetBoxModelFilterSet):
    label = MultiValueCharFilter()
    start_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name="start_structure",
        queryset=Structure.objects.all(),
        distinct=False,
        label="Start Structure (ID)",
    )
    end_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name="end_structure",
        queryset=Structure.objects.all(),
        distinct=False,
        label="End Structure (ID)",
    )
    start_face = django_filters.MultipleChoiceFilter(
        choices=BankFaceChoices,
        distinct=False,
        null_value=None,
    )
    end_face = django_filters.MultipleChoiceFilter(
        choices=BankFaceChoices,
        distinct=False,
        null_value=None,
    )
    configuration = django_filters.MultipleChoiceFilter(
        choices=ConduitBankConfigChoices,
        distinct=False,
        null_value=None,
    )
    encasement_type = django_filters.MultipleChoiceFilter(
        choices=EncasementTypeChoices,
        distinct=False,
        null_value=None,
    )
    total_conduits = MultiValueNumberFilter()
    length = MultiValueNumberFilter()

    class Meta:
        model = ConduitBank
        fields = ["id", "installation_date", "commissioned_date"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(label__icontains=value) | Q(comments__icontains=value))


class ConduitJunctionFilterSet(NetBoxModelFilterSet):
    label = MultiValueCharFilter()
    trunk_conduit_id = django_filters.ModelMultipleChoiceFilter(
        field_name="trunk_conduit",
        queryset=Conduit.objects.all(),
        distinct=False,
        label="Trunk Conduit (ID)",
    )
    branch_conduit_id = django_filters.ModelMultipleChoiceFilter(
        field_name="branch_conduit",
        queryset=Conduit.objects.all(),
        distinct=False,
        label="Branch Conduit (ID)",
    )
    towards_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name="towards_structure",
        queryset=Structure.objects.all(),
        distinct=False,
        label="Towards Structure (ID)",
    )
    position_on_trunk = MultiValueNumberFilter()

    class Meta:
        model = ConduitJunction
        fields = ["id"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(label__icontains=value) | Q(comments__icontains=value))


class CableSegmentFilterSet(NetBoxModelFilterSet):
    cable_id = django_filters.ModelMultipleChoiceFilter(
        field_name="cable",
        queryset=Cable.objects.all(),
        distinct=False,
        label="Cable (ID)",
    )
    pathway_id = django_filters.ModelMultipleChoiceFilter(
        field_name="pathway",
        queryset=Pathway.objects.all(),
        distinct=False,
        label="Pathway (ID)",
    )
    sequence = MultiValueNumberFilter()

    class Meta:
        model = CableSegment
        fields = ["id"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(comments__icontains=value))


class PathwayLocationFilterSet(NetBoxModelFilterSet):
    pathway_id = django_filters.ModelMultipleChoiceFilter(
        field_name="pathway",
        queryset=Pathway.objects.all(),
        distinct=False,
        label="Pathway (ID)",
    )
    site_id = django_filters.ModelMultipleChoiceFilter(
        field_name="site",
        queryset=Site.objects.all(),
        distinct=False,
        label="Site (ID)",
    )
    site = django_filters.ModelMultipleChoiceFilter(
        field_name="site__slug",
        queryset=Site.objects.all(),
        to_field_name="slug",
        distinct=False,
        label="Site (slug)",
    )
    location_id = django_filters.ModelMultipleChoiceFilter(
        field_name="location",
        queryset=Location.objects.all(),
        distinct=False,
        label="Location (ID)",
    )
    location = django_filters.ModelMultipleChoiceFilter(
        field_name="location__slug",
        queryset=Location.objects.all(),
        to_field_name="slug",
        distinct=False,
        label="Location (slug)",
    )
    sequence = MultiValueNumberFilter()

    class Meta:
        model = PathwayLocation
        fields = ["id"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(comments__icontains=value))


class SiteGeometryFilterSet(NetBoxModelFilterSet):
    site_id = django_filters.ModelMultipleChoiceFilter(
        field_name="site",
        queryset=Site.objects.all(),
        distinct=False,
        label="Site (ID)",
    )
    site = django_filters.ModelMultipleChoiceFilter(
        field_name="site__slug",
        queryset=Site.objects.all(),
        to_field_name="slug",
        distinct=False,
        label="Site (slug)",
    )
    structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name="structure",
        queryset=Structure.objects.all(),
        distinct=False,
        label="Structure (ID)",
    )

    class Meta:
        model = SiteGeometry
        fields = ["id"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(site__name__icontains=value))


class CircuitGeometryFilterSet(NetBoxModelFilterSet):
    circuit_id = django_filters.ModelMultipleChoiceFilter(
        field_name="circuit",
        queryset=Circuit.objects.all(),
        distinct=False,
        label="Circuit (ID)",
    )
    provider_id = django_filters.ModelMultipleChoiceFilter(
        field_name="circuit__provider",
        queryset=Provider.objects.all(),
        distinct=False,
        label="Provider (ID)",
    )
    provider = django_filters.ModelMultipleChoiceFilter(
        field_name="circuit__provider__slug",
        queryset=Provider.objects.all(),
        to_field_name="slug",
        distinct=False,
        label="Provider (slug)",
    )
    provider_reference = MultiValueCharFilter()

    class Meta:
        model = CircuitGeometry
        fields = ["id"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(circuit__cid__icontains=value) | Q(provider_reference__icontains=value))


class PlannedRouteFilterSet(TenancyFilterSet, NetBoxModelFilterSet):
    status = django_filters.MultipleChoiceFilter(
        choices=PlannedRouteStatusChoices,
        distinct=False,
    )
    start_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name="start_structure",
        queryset=Structure.objects.all(),
        distinct=False,
        label="Start Structure (ID)",
    )
    end_structure_id = django_filters.ModelMultipleChoiceFilter(
        field_name="end_structure",
        queryset=Structure.objects.all(),
        distinct=False,
        label="End Structure (ID)",
    )
    start_location_id = django_filters.ModelMultipleChoiceFilter(
        field_name="start_location",
        queryset=Location.objects.all(),
        distinct=False,
        label="Start Location (ID)",
    )
    end_location_id = django_filters.ModelMultipleChoiceFilter(
        field_name="end_location",
        queryset=Location.objects.all(),
        distinct=False,
        label="End Location (ID)",
    )
    cable_id = django_filters.ModelMultipleChoiceFilter(
        field_name="cable",
        queryset=Cable.objects.all(),
        distinct=False,
        label="Cable (ID)",
    )

    class Meta:
        model = PlannedRoute
        fields = ["id", "name", "status"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(comments__icontains=value))

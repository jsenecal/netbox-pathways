import re

import django_filters
from circuits.models import Circuit, Provider
from dcim.models import Cable, Location, Site
from django.core.exceptions import ValidationError
from django.db.models import Exists, OuterRef, Q
from netbox.filtersets import NetBoxModelFilterSet
from tenancy.filtersets import TenancyFilterSet
from tenancy.models import Tenant
from utilities.filters import MultiValueCharFilter, MultiValueNumberFilter

from .anchors import cable_end_nodes
from .choices import (
    AerialTypeChoices,
    BankFaceChoices,
    ConduitBankConfigChoices,
    ConduitMaterialChoices,
    EncasementTypeChoices,
    PathwayStatusChoices,
    PathwayTypeChoices,
    PlannedRouteStatusChoices,
    StructureStatusChoices,
    StructureTypeChoices,
)
from .graph import NODE_KINDS, pathways_connected_to
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

NODE_REF_RE = re.compile(rf"^(?:{'|'.join(NODE_KINDS)}):[0-9]+$")
CABLE_END_REF_RE = re.compile(r"^[0-9]+:[AB]$")


def validate_node_ref(value):
    """Validate one `connected_to` value.

    Validation belongs on the field rather than in the filter method: a
    ValidationError raised inside a `method=` callable surfaces as a 500,
    whereas a field error becomes filterset form errors, which DRF renders as
    a 400.
    """
    if value and value != "null" and not NODE_REF_RE.match(value):
        raise ValidationError(f"Enter a node reference as '<kind>:<pk>', where kind is one of {', '.join(NODE_KINDS)}.")


def validate_cable_end_ref(value):
    """Validate one `connected_to_cable_end` value.

    On the field rather than in the method, for the same reason as
    `validate_node_ref`.
    """
    if value and value != "null" and not CABLE_END_REF_RE.match(value):
        raise ValidationError("Enter a cable end as '<cable_pk>:A' or '<cable_pk>:B'.")


class GeoLengthFilterMixin(django_filters.FilterSet):
    """Adds `geo_length__gte` and `geo_length__lte` range filters that
    apply `PathwayQuerySet.with_geo_length()` so filtering happens at the
    PostGIS layer (`ST_Length`), not in Python.

    Subclasses `django_filters.FilterSet` so django-filter's metaclass
    collects the filter declarations into derived FilterSets' `base_filters`.
    """

    geo_length__gte = django_filters.NumberFilter(
        method="filter_geo_length",
        label="Geo length (m) >=",
    )
    geo_length__lte = django_filters.NumberFilter(
        method="filter_geo_length",
        label="Geo length (m) <=",
    )

    def filter_geo_length(self, queryset, name, value):
        if value is None or not hasattr(queryset, "with_geo_length"):
            return queryset
        lookup = "_geo_length__gte" if name.endswith("__gte") else "_geo_length__lte"
        return queryset.with_geo_length().filter(**{lookup: value})


class PathwayStatusFilterMixin(django_filters.FilterSet):
    """Adds the `status` filter shared by Pathway and all its subclasses."""

    status = django_filters.MultipleChoiceFilter(
        choices=PathwayStatusChoices,
        distinct=False,
        null_value=None,
    )


def occupied_pathways_q():
    """Q matching pathway rows that carry a cable, directly or by containment.

    A row is occupied when a CableSegment routes through it, through an
    innerduct it hosts (conduits), or through a member conduit or that
    conduit's innerducts (banks). Subtypes share the base Pathway pk, so the
    non-applicable arms simply never match and one expression serves the base
    queryset and every subclass.
    """
    segments = CableSegment.objects
    return (
        Q(Exists(segments.filter(pathway_id=OuterRef("pk"))))
        | Q(Exists(segments.filter(pathway__innerduct__parent_conduit_id=OuterRef("pk"))))
        | Q(Exists(segments.filter(pathway__conduit__conduit_bank_id=OuterRef("pk"))))
        | Q(Exists(segments.filter(pathway__innerduct__parent_conduit__conduit_bank_id=OuterRef("pk"))))
    )


def occupied_structures_q():
    """Q matching structures that terminate a pathway carrying a cable.

    Containment needs no arms of its own here: innerducts inherit their
    parent conduit's endpoints on save, so the segment-bearing pathway always
    references the physical structures directly.
    """
    routed = CableSegment.objects.filter(
        Q(pathway__start_structure_id=OuterRef("pk")) | Q(pathway__end_structure_id=OuterRef("pk"))
    )
    return Q(Exists(routed))


class OccupiedFilterMixin(django_filters.FilterSet):
    """Adds the `occupied` filter shared by Pathway and all its subclasses."""

    occupied = django_filters.BooleanFilter(
        method="filter_occupied",
        label="Occupied (has routed cables)",
    )

    def filter_occupied(self, queryset, name, value):
        if value:
            return queryset.filter(occupied_pathways_q())
        return queryset.exclude(occupied_pathways_q())


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
        if value:
            return queryset.filter(occupied_structures_q())
        return queryset.exclude(occupied_structures_q())

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


class PathwayFilterSet(
    OccupiedFilterMixin, PathwayStatusFilterMixin, GeoLengthFilterMixin, TenancyFilterSet, NetBoxModelFilterSet
):
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
    connected_to = MultiValueCharFilter(
        method="filter_connected_to",
        validators=[validate_node_ref],
        label="Connected to graph node (kind:pk)",
    )
    connected_to_cable_end = MultiValueCharFilter(
        method="filter_connected_to_cable_end",
        validators=[validate_cable_end_ref],
        label="Connected to a cable end (cable_pk:A|B)",
    )

    class Meta:
        model = Pathway
        fields = ["id", "installation_date", "commissioned_date"]

    def filter_connected_to(self, queryset, name, value):
        """Restrict to pathways touching any of the given graph nodes.

        Values are `kind:pk`, repeated for several nodes. `null` is skipped so
        an unset param from NetBox's APISelect is a no-op instead of matching
        nothing.
        """
        nodes = []
        for raw in value:
            if not raw or raw == "null":
                continue
            kind, _, pk = raw.partition(":")
            nodes.append((kind, int(pk)))
        if not nodes:
            return queryset
        return queryset.filter(pk__in=pathways_connected_to(nodes).values("pk"))

    def filter_connected_to_cable_end(self, queryset, name, value):
        """Restrict to pathways one end of a cable could plausibly enter.

        Values are `<cable_pk>:A` or `<cable_pk>:B`; `null` is skipped as it is
        for `connected_to`. The anchor is resolved here rather than by the
        caller so the URL carries one parameter however many candidate nodes
        the cable end has: a Site modeling an exchange area holds hundreds or
        thousands of structures, and a param per node overruns nginx's header
        buffers and Django's DATA_UPLOAD_MAX_NUMBER_FIELDS -- which TomSelect
        reports as "no results found", an empty picker with no explanation.

        A cable that does not exist, or an end that cannot be placed in the
        plant, matches nothing: the caller asked for a filter. Deciding not to
        filter at all is the view's job, since an empty picker is the bug.
        """
        refs = []
        for raw in value:
            if not raw or raw == "null":
                continue
            cable_pk, _, cable_end = raw.partition(":")
            refs.append((int(cable_pk), cable_end))
        if not refs:
            return queryset

        cables = Cable.objects.in_bulk({pk for pk, _ in refs})
        nodes = []
        for cable_pk, cable_end in refs:
            cable = cables.get(cable_pk)
            if cable is not None:
                nodes.extend(cable_end_nodes(cable, cable_end).nodes)
        if not nodes:
            return queryset.none()
        return queryset.filter(pk__in=pathways_connected_to(nodes).values("pk"))

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


class ConduitFilterSet(OccupiedFilterMixin, PathwayStatusFilterMixin, GeoLengthFilterMixin, NetBoxModelFilterSet):
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


class AerialSpanFilterSet(OccupiedFilterMixin, PathwayStatusFilterMixin, GeoLengthFilterMixin, NetBoxModelFilterSet):
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
    start_attachment_height = MultiValueNumberFilter()
    end_attachment_height = MultiValueNumberFilter()
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


class DirectBuriedFilterSet(OccupiedFilterMixin, PathwayStatusFilterMixin, GeoLengthFilterMixin, NetBoxModelFilterSet):
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


class InnerductFilterSet(OccupiedFilterMixin, PathwayStatusFilterMixin, GeoLengthFilterMixin, NetBoxModelFilterSet):
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


class ConduitBankFilterSet(
    OccupiedFilterMixin, PathwayStatusFilterMixin, GeoLengthFilterMixin, TenancyFilterSet, NetBoxModelFilterSet
):
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
    lashed_with_id = django_filters.ModelMultipleChoiceFilter(
        field_name="lashed_with",
        queryset=CableSegment.objects.all(),
        distinct=False,
        label="Lashed with segment (ID)",
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

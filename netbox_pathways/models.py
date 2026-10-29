from circuits.models import Circuit
from dcim.models import Cable, Location, Site
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.gis.db.models.functions import Length
from django.contrib.postgres.indexes import GistIndex
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import transaction
from django.db.models import OuterRef, Q, Subquery
from django.urls import reverse
from netbox.models import NetBoxModel
from netbox.models.ltree import LtreeModel, LtreeQuerySet
from tenancy.models import Tenant
from utilities.fields import ColorField
from utilities.querysets import RestrictedQuerySet

from .attachment import refresh_for_locations, refresh_for_site, resolve_anchor
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
from .geo import get_srid
from .landing import attaches, end_point, is_area, landing_on, reference_point, with_end
from .pathway_types import (
    DRAWN_TYPES,
    PATHWAY_TYPES,
    TYPE_SPECIFIC_FIELDS_ORDERED,
    UNROUTABLE_TYPES,
    allowed_child_types,
    inapplicable_fields,
    spec_or_untyped,
)

ENDPOINT_TOLERANCE = 1.0


class Structure(NetBoxModel):
    name = models.CharField(max_length=100, unique=True)
    status = models.CharField(
        max_length=50,
        choices=StructureStatusChoices,
        default=StructureStatusChoices.STATUS_ACTIVE,
    )
    structure_type = models.CharField(max_length=50, choices=StructureTypeChoices, blank=True)
    site = models.ForeignKey(
        Site,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pathways_structures",
    )
    location = models.OneToOneField(
        Location,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pathways_structure",
        help_text="dcim.Location that this structure physically is (e.g. a handhole modelled as a Location)",
    )
    geometry = models.GeometryField(
        srid=get_srid(),
        help_text="Geographic geometry (point for simple structures, polygon for footprints)",
    )
    elevation = models.FloatField(null=True, blank=True, help_text="Elevation in meters")
    height = models.FloatField(null=True, blank=True, help_text="Height in meters")
    width = models.FloatField(null=True, blank=True, help_text="Width in meters")
    length = models.FloatField(null=True, blank=True, help_text="Length in meters")
    depth = models.FloatField(null=True, blank=True, help_text="Depth in meters")
    installation_date = models.DateField(null=True, blank=True)
    commissioned_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date the structure was commissioned / handed over (often after installation_date)",
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pathways_structures",
    )
    installed_by = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="installed_pathways_structures",
        help_text="Contractor or workforce that physically installed this structure",
    )
    access_notes = models.TextField(blank=True, help_text="Access restrictions or requirements")
    comments = models.TextField(blank=True)

    clone_fields = (
        "status",
        "structure_type",
        "site",
        "tenant",
        "installed_by",
        "installation_date",
        "commissioned_date",
        "height",
        "width",
        "length",
        "depth",
    )

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["structure_type"]),
            models.Index(fields=["site"]),
            models.Index(fields=["status"]),
            models.Index(fields=["installed_by"]),
        ]

    def get_status_color(self):
        return StructureStatusChoices.colors.get(self.status)

    @property
    def centroid(self):
        """Return the centroid point regardless of geometry type."""
        if self.geometry is None:
            return None
        if self.geometry.geom_type == "Point":
            return self.geometry
        return self.geometry.centroid

    def clean(self):
        super().clean()
        if self.location_id:
            if self.site_id and self.location.site_id != self.site_id:
                raise ValidationError({"location": f"Location {self.location} does not belong to site {self.site}."})
            # Structure.site is nullable (Device.site is not), so a location
            # without a site completes it rather than being rejected -- that
            # keeps the site-centroid map fallback working.
            if not self.site_id:
                self.site = self.location.site

    def save(self, *args, **kwargs):
        # Read the stored geometry rather than tracking it on the instance:
        # immune to in-place GEOS mutation, and free when structures are
        # loaded in bulk for the map.
        # Store and compare in the plugin SRID: the REST API hands GeoJSON over
        # as EPSG:4326, and pathway paths must not be moved in degrees.
        srid = get_srid()
        if self.geometry is not None and self.geometry.srid not in (None, srid):
            self.geometry = self.geometry.transform(srid, clone=True)
        update_fields = kwargs.get("update_fields")
        geometry_saved = update_fields is None or "geometry" in update_fields
        location_saved = update_fields is None or "location" in update_fields
        old_geom = old_location_id = None
        if self.pk:
            old_geom, old_location_id = Structure.objects.filter(pk=self.pk).values_list(
                "geometry", "location_id"
            ).first() or (None, None)
        with transaction.atomic():
            super().save(*args, **kwargs)
            if location_saved and old_location_id != self.location_id:
                # Pathway ends under the old and new location now attach elsewhere.
                old_location = Location.objects.filter(pk=old_location_id).first() if old_location_id else None
                refresh_for_locations([old_location, self.location])
            if (
                geometry_saved
                and old_geom is not None
                and self.geometry is not None
                and not old_geom.equals_exact(self.geometry)
            ):
                from .reanchor import reanchor_structure

                reanchor_structure(self, old_geom)

    def __str__(self):
        if self.structure_type:
            return f"{self.name} ({self.get_structure_type_display()})"
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_pathways:structure", args=[self.pk])

    @property
    def map_container(self):
        """The drawn map feature that stands for this structure: itself."""
        return self

    @property
    def map_select_id(self):
        """The feature id the map uses for `?select=`."""
        return f"structure-{self.pk}"


class SiteGeometry(NetBoxModel):
    """
    Links a NetBox Site to pathways infrastructure.

    Optionally associates a Structure (the Site IS this Structure), and
    provides a geometry field for the site boundary/footprint.  When a
    structure is linked and no explicit geometry is set, the geometry is
    copied from the structure on save.
    """

    site = models.OneToOneField(
        Site,
        on_delete=models.CASCADE,
        related_name="pathways_geometry",
    )
    structure = models.OneToOneField(
        "Structure",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="site_geometry",
        help_text="Structure that physically represents this site",
    )
    geometry = models.GeometryField(
        srid=get_srid(),
        null=True,
        blank=True,
        help_text="Site boundary or footprint — auto-populated from structure if blank",
    )
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ["site"]
        verbose_name = "Site Geometry"
        verbose_name_plural = "Site Geometries"

    @property
    def effective_geometry(self):
        """Return explicit geometry, or fall back to linked structure's geometry."""
        if self.geometry:
            return self.geometry
        if self.structure_id and self.structure.geometry:
            return self.structure.geometry
        return None

    def __str__(self):
        return f"Geometry: {self.site.name}"

    def get_absolute_url(self):
        return reverse("plugins:netbox_pathways:sitegeometry", args=[self.pk])

    def save(self, *args, **kwargs):
        if self.structure_id and not self.geometry:
            self.geometry = self.structure.geometry
        old_structure_id = None
        if self.pk:
            old_structure_id = SiteGeometry.objects.filter(pk=self.pk).values_list("structure_id", flat=True).first()
        created = self.pk is None
        with transaction.atomic():
            super().save(*args, **kwargs)
            # Only the linked structure decides what the site's locations
            # attach to; a redrawn boundary changes nothing.
            if created or old_structure_id != self.structure_id:
                refresh_for_site(self.site_id)


class CircuitGeometry(NetBoxModel):
    """
    Stores a provider-described route geometry for a native NetBox Circuit.

    The circuit itself is a black box — this just records the geographic path
    the provider says the circuit follows, for display on the infrastructure map.
    """

    circuit = models.OneToOneField(
        Circuit,
        on_delete=models.CASCADE,
        related_name="pathways_route",
    )
    path = models.LineStringField(
        srid=get_srid(),
        help_text="Provider-described route as a LineString",
    )
    provider_reference = models.CharField(
        max_length=200,
        blank=True,
        help_text="Provider's route/span ID or document reference",
    )
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ["circuit"]
        verbose_name = "Circuit Geometry"
        verbose_name_plural = "Circuit Geometries"

    def __str__(self):
        return f"Route: {self.circuit.cid}"

    def get_absolute_url(self):
        return reverse("plugins:netbox_pathways:circuitgeometry", args=[self.pk])


def _distance_to_m(value):
    """Coerce a GeoDjango Distance (or numeric) to rounded metres.

    geo_length is a display value and GPS accuracy tops out around
    centimetres, so it is rounded to 2 decimals by default; deployments
    adjust via `PLUGINS_CONFIG['netbox_pathways']['geo_length_decimals']`
    (0 = whole metres).
    """
    if value is None:
        return None
    metres = value.m if hasattr(value, "m") else float(value)
    decimals = settings.PLUGINS_CONFIG.get("netbox_pathways", {}).get("geo_length_decimals", 2)
    if decimals <= 0:
        return round(metres)
    return round(metres, decimals)


def touching_q(structure, direct=False, lookup="", prefix=""):
    """Q for pathways with an end attached to `structure`.

    `structure` is anything a structure FK lookup accepts (an instance, a pk,
    an OuterRef); with lookup="__in", a collection of them. `prefix` reaches
    the pathway through a relation (e.g. "pathway__" from a cable segment).

    By default the stored anchors decide: an end naming a location inside
    the structure's site or location tree counts (attachment.resolve_anchor,
    docs/user-guide/attachment.md). With direct=True only the
    start/end_structure fields count -- the route graph's notion, which
    keeps locations as places of their own.
    """
    field = "structure" if direct else "anchor"
    return Q(**{f"{prefix}start_{field}{lookup}": structure}) | Q(**{f"{prefix}end_{field}{lookup}": structure})


class PathwayQuerySet(LtreeQuerySet):
    def touching(self, structure, direct=False):
        """Pathways with an end attached to `structure`; see touching_q()."""
        return self.filter(touching_q(structure, direct=direct))

    def with_geo_length(self):
        """Annotate each pathway with `_geo_length`: PostGIS `ST_Length(geometry)`."""
        return self.annotate(_geo_length=Length("geometry"))

    def with_route_geometry(self):
        """Annotate each pathway with `_route_geometry`; see Pathway.route_geometry."""
        nearest = (
            Pathway.objects.filter(path__ancestor_or_equal=OuterRef("path"), geometry__isnull=False)
            .order_by("-path")
            .values("geometry")[:1]
        )
        return self.annotate(_route_geometry=Subquery(nearest, output_field=models.LineStringField()))

    def map_containers(self):
        """Pathways drawn on the map: top-level pathways of a drawn type.

        Anything else (innerducts, trays, raceways, any pathway with a
        parent) is shown through its map_container instead.
        """
        return self.filter(pathway_type__in=DRAWN_TYPES, parent__isnull=True)

    def routable(self):
        """Pathways cables can be routed through: every type but containers such as banks."""
        return self.exclude(pathway_type__in=UNROUTABLE_TYPES)


# Pathway types that never have a parent, and those that always do. Sorted so
# the database constraints built from them deconstruct identically every run.
TOP_LEVEL_TYPES = sorted(t for t, s in PATHWAY_TYPES.items() if not s.parents)
PARENTED_TYPES = sorted(t for t, s in PATHWAY_TYPES.items() if s.parent_required)


class Pathway(LtreeModel, NetBoxModel):
    """A physical pathway of any type, optionally contained in a parent pathway.

    `pathway_type` selects which of the type-specific columns apply and what
    the pathway may sit inside; pathway_types.py holds those rules. The
    hierarchy is an ltree: `path` is maintained by database triggers from
    `parent`, so ancestor and descendant lookups are single queries.
    """

    prerequisite_models = ("netbox_pathways.Structure",)

    objects = PathwayQuerySet.as_manager()

    label = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=50,
        choices=PathwayStatusChoices,
        default=PathwayStatusChoices.STATUS_ACTIVE,
    )
    pathway_type = models.CharField(max_length=50, choices=PathwayTypeChoices)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        help_text="Pathway this one runs inside (e.g. the bank of a conduit, the conduit of an innerduct)",
    )
    geometry = models.LineStringField(
        srid=get_srid(),
        null=True,
        blank=True,
        help_text="Route geometry (not applicable to indoor pathways between two locations)",
    )
    start_structure = models.ForeignKey(
        Structure,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pathways_out",
    )
    end_structure = models.ForeignKey(
        Structure,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pathways_in",
    )
    start_location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pathways_out",
    )
    end_location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pathways_in",
    )
    # Derived, never edited: the structure each end attaches to under
    # attachment.resolve_anchor(). Stored so pages, filters and the API can
    # ask "which pathways are this structure's?" in SQL.
    start_anchor = models.ForeignKey(
        Structure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="pathways_anchored_start",
    )
    end_anchor = models.ForeignKey(
        Structure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="pathways_anchored_end",
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pathways_pathways",
    )
    installed_by = models.ForeignKey(
        Tenant,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="installed_pathways_pathways",
        help_text="Contractor or workforce that physically installed this pathway",
    )
    length = models.FloatField(null=True, blank=True, help_text="Total length in meters")
    installation_date = models.DateField(null=True, blank=True)
    commissioned_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date the pathway was commissioned / accepted (often after installation_date)",
    )
    comments = models.TextField(blank=True)

    # Type-specific columns. Which apply to which type is pathway_types.py's
    # call; save() clears the ones that do not apply to the current type.

    # Conduit bank and conduit
    start_face = models.CharField(
        max_length=50,
        choices=BankFaceChoices,
        blank=True,
        help_text="Which face/wall of the start structure",
    )
    end_face = models.CharField(
        max_length=50,
        choices=BankFaceChoices,
        blank=True,
        help_text="Which face/wall of the end structure",
    )
    # Conduit bank
    configuration = models.CharField(
        max_length=50,
        choices=ConduitBankConfigChoices,
        blank=True,
        help_text="Layout configuration (e.g., 2x2, 3x3) -- leave blank if irregular",
    )
    total_conduits = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Designed conduit capacity of the bank (leave blank if unknown)",
    )
    height = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of duct rows (vertical count); leave blank if unknown",
    )
    width = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of duct columns (horizontal count); leave blank if unknown",
    )
    encasement_type = models.CharField(max_length=50, choices=EncasementTypeChoices, blank=True)
    # Conduit
    material = models.CharField(max_length=50, choices=ConduitMaterialChoices, blank=True)
    inner_diameter = models.FloatField(null=True, blank=True, help_text="Inner diameter in millimeters")
    outer_diameter = models.FloatField(null=True, blank=True, help_text="Outer diameter in millimeters")
    depth = models.FloatField(null=True, blank=True, help_text="Burial depth in meters")
    start_junction = models.ForeignKey(
        "ConduitJunction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conduits_from",
    )
    end_junction = models.ForeignKey(
        "ConduitJunction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conduits_to",
    )
    # Conduit and innerduct
    position = models.CharField(
        max_length=50,
        blank=True,
        help_text="Position within the parent pathway (e.g., A1 in a bank)",
    )
    # Aerial span
    aerial_type = models.CharField(max_length=50, choices=AerialTypeChoices, blank=True)
    start_attachment_height = models.FloatField(
        null=True,
        blank=True,
        help_text="Attachment height at the start endpoint, in meters",
    )
    end_attachment_height = models.FloatField(
        null=True,
        blank=True,
        help_text="Attachment height at the end endpoint, in meters",
    )
    sag = models.FloatField(null=True, blank=True, help_text="Cable sag in meters")
    messenger_size = models.CharField(max_length=50, blank=True, help_text="Messenger wire size/type")
    wind_loading = models.CharField(max_length=50, blank=True, help_text="Wind loading zone/rating")
    ice_loading = models.CharField(max_length=50, blank=True, help_text="Ice loading zone/rating")
    # Direct buried
    burial_depth = models.FloatField(null=True, blank=True, help_text="Burial depth in meters")
    warning_tape = models.BooleanField(default=False, help_text="Warning tape installed above cable")
    tracer_wire = models.BooleanField(default=False, help_text="Tracer wire installed with cable")
    armor_type = models.CharField(max_length=100, blank=True, help_text="Cable armor type if applicable")
    # Innerduct
    size = models.CharField(max_length=50, blank=True, help_text='Innerduct size (e.g., 1.25", 32mm)')
    color = ColorField(blank=True, help_text="Innerduct color for identification")

    # Every type-specific field except position, which identifies a single
    # slot in the parent and so is never copied.
    clone_fields = (
        "pathway_type",
        "parent",
        "status",
        "start_structure",
        "end_structure",
        "start_location",
        "end_location",
        "tenant",
        "installed_by",
        "installation_date",
        "commissioned_date",
        *(name for name in TYPE_SPECIFIC_FIELDS_ORDERED if name != "position"),
    )

    class Meta:
        ordering = ["pk"]
        indexes = [
            models.Index(fields=["pathway_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["start_structure", "end_structure"]),
            models.Index(fields=["material"]),
            models.Index(fields=["aerial_type"]),
            GistIndex(fields=["path"], name="netbox_path_pathway_path_gist"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~Q(pathway_type__in=PARENTED_TYPES) | Q(parent__isnull=False),
                name="pathway_parent_required",
                violation_error_message="This pathway type must have a parent.",
            ),
            models.CheckConstraint(
                condition=~Q(pathway_type__in=TOP_LEVEL_TYPES) | Q(parent__isnull=True),
                name="pathway_parent_forbidden",
                violation_error_message="This pathway type cannot have a parent.",
            ),
            # A condition cannot see the parent's type, so this also covers
            # conduits in a raceway, not only conduits in a bank.
            models.UniqueConstraint(
                fields=["parent", "position"],
                condition=Q(pathway_type="conduit", parent__isnull=False, position__gt=""),
                name="unique_conduit_position_in_parent",
                violation_error_message="Another conduit already occupies this position in the parent.",
            ),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pk = self.__dict__.get("id")

    def get_status_color(self):
        return PathwayStatusChoices.colors.get(self.status)

    @property
    def spec(self):
        """This pathway's PathwayTypeSpec; UNTYPED for an unknown or blank type."""
        return spec_or_untyped(self.pathway_type)

    @property
    def endpoint_kinds(self):
        """What one pathway side may name; exactly one of them per side."""
        return self.spec.endpoint_kinds

    @property
    def start_endpoint(self):
        return self.start_structure or self.start_location

    @property
    def end_endpoint(self):
        return self.end_structure or self.end_location

    @property
    def is_indoor(self):
        """Both endpoints are dcim.Locations, which carry no geometry.

        Junction endpoints are geographic, so they preclude indoor status.
        """
        return bool(
            self.start_location_id
            and self.end_location_id
            and not self.start_structure_id
            and not self.end_structure_id
            and not self.start_junction_id
            and not self.end_junction_id
        )

    @property
    def geo_length(self):
        """Length of `geometry` in metres, computed by PostGIS `ST_Length`.

        Reuses `_geo_length` when the instance was loaded via
        `Pathway.objects.with_geo_length()`; otherwise issues an annotated
        query so the length still comes from PostGIS, not Python.
        Distinct from `length`, which is the manually entered as-built value.
        """
        annotated = self.__dict__.get("_geo_length")
        if annotated is not None:
            return _distance_to_m(annotated)
        if self.pk is None:
            return None
        value = Pathway.objects.with_geo_length().values_list("_geo_length", flat=True).get(pk=self.pk)
        return _distance_to_m(value)

    @property
    def requires_geometry(self):
        """Whether clean() demands a route geometry.

        A pathway with a parent follows its parent's route, and an indoor
        pathway (both endpoints are locations) has no geographic route.
        """
        return not self.parent_id and not self.is_indoor

    @property
    def route_geometry(self):
        """Own geometry, or the nearest ancestor's when this pathway has none.

        A pathway with a parent needs no geometry of its own (see
        requires_geometry): it runs along its container. Reuses
        `_route_geometry` when the instance was loaded via
        `Pathway.objects.with_route_geometry()`; otherwise one ancestor
        query, whose answer is kept while the parent is unchanged.
        """
        if "_route_geometry" in self.__dict__:
            return self.__dict__["_route_geometry"]
        if self.geometry is not None or self.parent_id is None:
            return self.geometry
        cached = self.__dict__.get("_ancestor_geometry")
        if cached is not None and cached[0] == self.parent_id:
            return cached[1]
        geometry = (
            self._parent_and_ancestors()
            .filter(geometry__isnull=False)
            .order_by("-path")
            .values_list("geometry", flat=True)
            .first()
        )
        self.__dict__["_ancestor_geometry"] = (self.parent_id, geometry)
        return geometry

    def _parent_and_ancestors(self):
        """The parent and everything above it, outermost first.

        Resolved from the parent's stored ltree path rather than this
        instance's `path`, so an instance loaded before an ancestor moved
        still sees the current hierarchy.
        """
        parent_path = Pathway.objects.filter(pk=self.parent_id).values("path")
        return Pathway.objects.filter(path__ancestor_or_equal=Subquery(parent_path)).order_by("path")

    @property
    def map_container(self):
        """The drawn map feature that stands for this pathway, or None.

        The outermost pathway of this one's tree (itself when top-level),
        when that is of a drawn type; None when nothing above it is drawn
        (e.g. a conduit in a raceway).
        """
        if self.parent_id is None:
            root = self
        else:
            root = self._parent_and_ancestors().filter(parent__isnull=True).first()
        if root is None or root.pathway_type not in DRAWN_TYPES:
            return None
        return root

    @property
    def map_select_id(self):
        """The feature id the map uses for `?select=`."""
        return f"{self.pathway_type}-{self.pk}"

    @property
    def effective_tenant(self):
        """Own tenant, or the nearest ancestor's when not set.

        Display-layer fallback in the NetBox VRF/prefix style: the stored
        field stays authoritative for filtering and the API.

        Walks the parents already loaded in memory first, so a list fetched
        with `select_related("parent__tenant")` (deeper for nested chains)
        costs no queries. Only the part of the chain that is not loaded is
        read, with one ancestor query whose answer is kept on that instance
        while its parent is unchanged, because tables read this several
        times per row.
        """
        node = self
        while node.tenant_id is None:
            if node.parent_id is None:
                return None
            if not Pathway.parent.is_cached(node):
                return node._unloaded_ancestor_tenant()
            node = node.parent
        return node.tenant

    def _unloaded_ancestor_tenant(self):
        """The nearest tenant above this pathway, read from the database once."""
        cached = self.__dict__.get("_ancestor_tenant")
        if cached is not None and cached[0] == self.parent_id:
            return cached[1]
        nearest = (
            self._parent_and_ancestors().filter(tenant__isnull=False).select_related("tenant").order_by("-path").first()
        )
        tenant = nearest.tenant if nearest else None
        self.__dict__["_ancestor_tenant"] = (self.parent_id, tenant)
        return tenant

    @property
    def attachment_height(self):
        """Mean of the two per-endpoint heights with None-tolerant fallback."""
        a = self.start_attachment_height
        b = self.end_attachment_height
        if a is None and b is None:
            return None
        if a is None:
            return b
        if b is None:
            return a
        return (a + b) / 2

    def clean(self):
        super().clean()  # LtreeModel rejects a parent that would create a cycle
        if self.pathway_type not in PATHWAY_TYPES:
            return  # clean_fields() already reports the invalid choice
        self.check_containment()
        # Inherit before validation so the endpoint checks and geometry
        # snapping see the effective endpoints.
        self._inherit_endpoints_from_parent()
        if self.spec.endpoints_required:
            self.check_endpoints_present()
        # Ambiguous sides first: straighten() would silently prefer the structure.
        self.check_one_endpoint_kind()
        if self.spec.derives_geometry:
            self.straighten()
        if not self.geometry:
            if self.requires_geometry:
                raise ValidationError(
                    {
                        "geometry": "Geometry is required unless the pathway has a parent "
                        "or both endpoints are locations (indoor pathway)."
                    }
                )
            return
        for side in ("start", "end"):
            geom, kind = self.anchor_geometry(side)
            if geom is not None and not self.is_indoor_end(side, geom):
                self._snap_geometry_end(side, geom, kind)

    def check_containment(self):
        """Enforce the containment rule from pathway_types.py.

        The parent must be of a type this one may sit in (or absent when the
        type cannot have one, present when it must), and existing children
        must still be allowed under the current type -- so changing a
        pathway's type cannot strand children it may no longer contain. The
        same goes for conduit junctions: a pathway that is a junction's trunk
        or branch keeps a type whose ends may hang from a junction.
        """
        rules = self.spec
        label = self.get_pathway_type_display()
        errors = {}
        if self.parent_id:
            if not rules.parents:
                errors["parent"] = f"A {label} cannot have a parent pathway."
            elif self.parent.pathway_type not in rules.parents:
                allowed = ", ".join(sorted(rules.parents))
                errors["parent"] = (
                    f"A {label} cannot be inside a {self.parent.get_pathway_type_display()} (allowed: {allowed})."
                )
        elif rules.parent_required:
            errors["parent"] = f"A {label} must have a parent pathway."
        if self.pk and "junction" not in rules.endpoint_kinds:
            # A junction's trunk and branch must be pathways whose type can
            # hang from a junction; ConduitJunction only checks that when the
            # junction itself is validated, not when its conduit is retyped.
            if ConduitJunction.objects.filter(Q(trunk_conduit_id=self.pk) | Q(branch_conduit_id=self.pk)).exists():
                errors["pathway_type"] = (
                    f"A {label} cannot be the trunk or branch of a conduit junction; "
                    "remove the junctions on this pathway first."
                )
        if self.pk:
            children = self.get_children().exclude(pathway_type__in=allowed_child_types(self.pathway_type))
            stranded = sorted({child.get_pathway_type_display() for child in children})
            if stranded:
                errors["pathway_type"] = (
                    f"A {label} cannot contain its existing children ({', '.join(stranded)}); "
                    "move or remove them first."
                )
        if errors:
            raise ValidationError(errors)

    def check_endpoints_present(self):
        """Require a start and an end (structure, location or junction)."""
        for side in ("start", "end"):
            if not any(getattr(self, f"{side}_{kind}_id") for kind in self.endpoint_kinds):
                raise ValidationError(
                    f"{self.get_pathway_type_display()} must have a {side} point "
                    f"({', '.join(self.endpoint_kinds[:-1])}, or {self.endpoint_kinds[-1]})"
                )

    def check_one_endpoint_kind(self):
        """Reject a side naming more than one of endpoint_kinds.

        A side naming both a structure and a location would be ambiguous
        about where the pathway ends; see docs/user-guide/attachment.md.
        """
        errors = {}
        for side in ("start", "end"):
            named = [kind for kind in self.endpoint_kinds if getattr(self, f"{side}_{kind}_id", None)]
            if len(named) > 1:
                errors[f"{side}_{named[-1]}"] = f"The {side} names a {' and a '.join(named)}; set only one."
        if errors:
            raise ValidationError(errors)

    def anchor_structure(self, side):
        """The structure one end is attached to, resolved live.

        The <side>_structure, else the nearest structure enclosing
        <side>_location -- see attachment.resolve_anchor() and
        docs/user-guide/attachment.md.
        """
        return resolve_anchor(getattr(self, f"{side}_structure", None), getattr(self, f"{side}_location", None))

    def is_indoor_end(self, side, geom):
        """Whether this end is an indoor position inside its area structure.

        True when the end names a location (not the structure itself), the
        structure it belongs to is an area (a building footprint), and the
        drawn end lies inside it: a room, not a building entry. Snapping,
        moving the structure and repair keep such an end's place inside the
        footprint; see docs/user-guide/attachment.md.
        """
        return (
            self.geometry is not None
            and getattr(self, f"{side}_structure_id", None) is None
            and getattr(self, f"{side}_location_id", None) is not None
            and is_area(geom)
            and geom.contains(end_point(self.geometry, side))
        )

    def resolved_anchor_ids(self, memo=None):
        """(start, end) pks of the structures the ends attach to, resolved live.

        `memo` (location pk -> structure pk) lets a batch resolve each named
        location once instead of once per pathway end.
        """
        ids = []
        for side in ("start", "end"):
            location_id = getattr(self, f"{side}_location_id", None)
            if memo is None or location_id is None or getattr(self, f"{side}_structure_id", None):
                ids.append(getattr(self.anchor_structure(side), "pk", None))
                continue
            if location_id not in memo:
                memo[location_id] = getattr(self.anchor_structure(side), "pk", None)
            ids.append(memo[location_id])
        return tuple(ids)

    def anchor_geometry(self, side):
        """Geometry one end must land on, and what it is.

        (geom, "structure"), (geom, "junction") for a type whose ends may
        hang from a junction on a trunk conduit, or (None, None).
        """
        structure = self.anchor_structure(side)
        if structure is not None and structure.geometry is not None:
            return structure.geometry, "structure"
        if "junction" in self.endpoint_kinds:
            junction = getattr(self, f"{side}_junction", None)
            junction_geom = junction.derived_geometry if junction is not None else None
            if junction_geom is not None:
                return junction_geom, "junction"
        return None, None

    def _snap_geometry_end(self, side, geom, kind):
        """Snap the geometry's <side> end to geom; raise if it is not attached.

        geom may be a Point or an area geometry (snapped to its boundary).
        kind names the endpoint type ("structure" or "junction") in the
        validation message.
        """
        endpoint = end_point(self.geometry, side)
        if not attaches(geom, endpoint, ENDPOINT_TOLERANCE):
            of_boundary = " of the boundary" if is_area(geom) else ""
            raise ValidationError(
                {
                    "geometry": f"Geometry {side} point is too far from the {side} {kind} "
                    f"(must be within {ENDPOINT_TOLERANCE}m{of_boundary})."
                }
            )
        self.geometry = with_end(self.geometry, side, landing_on(geom, endpoint))

    def straighten(self):
        """Rebuild geometry as the straight line between the two landings.

        For types whose geometry is derived from the endpoints (aerial
        spans). Both ends must hang from a structure with geometry -- a span
        cannot float. A point structure pins its end; an area structure
        (building) lands the end on its boundary nearest the submitted end,
        or nearest the other support when no path was submitted.
        """
        from django.contrib.gis.geos import LineString

        anchors = {side: self.anchor_structure(side) for side in ("start", "end")}
        detached = {
            f"{side}_structure": "Aerial spans must attach to a structure with geometry at both ends."
            for side, structure in anchors.items()
            if structure is None or structure.geometry is None
        }
        if detached:
            raise ValidationError(detached)
        if anchors["start"].pk == anchors["end"].pk:
            raise ValidationError({"end_structure": "An aerial span connects two different supports."})

        start_geom = anchors["start"].geometry
        end_geom = anchors["end"].geometry
        if self.geometry and self.geometry.srid != start_geom.srid:
            self.geometry = self.geometry.transform(start_geom.srid, clone=True)
        if self.geometry:
            start = landing_on(start_geom, end_point(self.geometry, "start"))
            end = landing_on(end_geom, end_point(self.geometry, "end"))
        else:
            start = landing_on(start_geom, reference_point(end_geom))
            end = landing_on(end_geom, start)
        self.geometry = LineString((start.x, start.y), (end.x, end.y), srid=start_geom.srid)

    def __str__(self):
        return self.label or f"#{self.pk or self._pk}"

    def get_absolute_url(self):
        return reverse("plugins:netbox_pathways:pathway", args=[self.pk])

    def _inherit_endpoints_from_parent(self):
        """Fill each side left unset from the parent pathway's same side.

        A side counts as set when it names any of this type's endpoint
        kinds; only the parent's structure and location are copied.
        """
        if not self.parent_id:
            return
        parent = self.parent
        for side in ("start", "end"):
            if any(getattr(self, f"{side}_{kind}_id", None) for kind in self.endpoint_kinds):
                continue
            setattr(self, f"{side}_structure", getattr(parent, f"{side}_structure"))
            setattr(self, f"{side}_location", getattr(parent, f"{side}_location"))

    def _clear_inapplicable_fields(self):
        """Reset the type-specific fields that do not apply to this type."""
        for name in inapplicable_fields(self.pathway_type):
            field = self._meta.get_field(name)
            setattr(self, field.attname, None if field.is_relation else field.get_default())

    def save(self, *args, **kwargs):
        if self.pathway_type in PATHWAY_TYPES:
            self._clear_inapplicable_fields()
            self._inherit_endpoints_from_parent()
        self.start_anchor_id, self.end_anchor_id = self.resolved_anchor_ids()
        super().save(*args, **kwargs)
        self._pk = self.pk


class ConduitJunction(NetBoxModel):
    prerequisite_models = ("netbox_pathways.Pathway",)

    label = models.CharField(max_length=100, blank=True)
    trunk_conduit = models.ForeignKey(
        Pathway,
        on_delete=models.CASCADE,
        limit_choices_to={"pathway_type": "conduit"},
        related_name="junctions_on_trunk",
    )
    branch_conduit = models.ForeignKey(
        Pathway,
        on_delete=models.CASCADE,
        limit_choices_to={"pathway_type": "conduit"},
        related_name="junction_as_branch",
    )
    towards_structure = models.ForeignKey(
        Structure,
        on_delete=models.PROTECT,
        help_text="Which end of trunk the junction faces",
    )
    position_on_trunk = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Position along trunk (0=start, 1=end)",
    )
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["trunk_conduit", "position_on_trunk"],
                name="unique_junction_position_on_trunk",
            ),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pk = self.__dict__.get("id")

    def __str__(self):
        return self.label or f"#{self.pk or self._pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._pk = self.pk

    def get_absolute_url(self):
        return reverse("plugins:netbox_pathways:conduitjunction", args=[self.pk])

    def clean(self):
        super().clean()
        if self.trunk_conduit and self.towards_structure:
            trunk_structures = [
                s
                for s in [
                    self.trunk_conduit.start_structure,
                    self.trunk_conduit.end_structure,
                ]
                if s is not None
            ]
            if trunk_structures and self.towards_structure not in trunk_structures:
                raise ValidationError("towards_structure must be one of the trunk conduit's structure endpoints")
            elif not trunk_structures:
                raise ValidationError(
                    "towards_structure cannot be set when the trunk conduit "
                    "has no structure endpoints (uses locations or junctions only)"
                )

    @property
    def derived_geometry(self):
        """Point on the trunk conduit's geometry at position_on_trunk.

        Derived, not stored: a junction carries no geometry column and no
        dcim.Location relation.
        """
        if self.trunk_conduit and self.trunk_conduit.geometry:
            return self.trunk_conduit.geometry.interpolate_normalized(self.position_on_trunk)
        return None


class PathwayLocation(NetBoxModel):
    """
    Records that a pathway passes through a specific location or site along its length.
    Ordered waypoints between the start and end endpoints.
    """

    prerequisite_models = ("netbox_pathways.Pathway",)

    pathway = models.ForeignKey(
        Pathway,
        on_delete=models.CASCADE,
        related_name="waypoints",
    )
    site = models.ForeignKey(
        Site,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pathway_waypoints",
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pathway_waypoints",
    )
    sequence = models.PositiveIntegerField(default=0, help_text="Order along the pathway")
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ["pathway", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["pathway", "sequence"],
                name="unique_pathway_location_sequence",
            ),
        ]

    def __str__(self):
        point = self.location or self.site
        return f"{self.pathway} @ {point} (seq {self.sequence})"

    def get_absolute_url(self):
        return reverse("plugins:netbox_pathways:pathwaylocation", args=[self.pk])

    def clean(self):
        super().clean()
        if not self.site and not self.location:
            raise ValidationError("At least one of site or location is required")


class CableSegmentQuerySet(RestrictedQuerySet):
    def route_of(self, cable):
        """`cable`'s segments in route order, with each pathway and its endpoints loaded.

        `cable` is a Cable or its pk.
        """
        return (
            self.filter(cable=cable)
            .select_related(
                "pathway",
                "pathway__start_structure",
                "pathway__end_structure",
                "pathway__start_location",
                "pathway__end_location",
            )
            .order_by("sequence")
        )


class CableSegment(NetBoxModel):
    prerequisite_models = ("netbox_pathways.Pathway",)

    objects = CableSegmentQuerySet.as_manager()

    cable = models.ForeignKey(Cable, on_delete=models.CASCADE, related_name="pathway_segments")
    pathway = models.ForeignKey(
        Pathway,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cable_segments",
    )
    sequence = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Order of segment in cable route (auto-assigned)",
    )
    lashed_with = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=True,
        help_text=(
            "Other cable segments mechanically lashed together with this one in aerial plant. "
            "Symmetrical: adding a peer here automatically adds this segment to the peer's "
            "lashed_with set. Lashing is per-segment because a cable can be partly overlashed "
            "(aerial segments) and partly not (underground segments along the same route)."
        ),
    )
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ["cable", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["cable", "sequence"],
                name="unique_cable_segment_sequence",
            ),
        ]

    def __str__(self):
        pw = self.pathway
        if pw:
            return f"{self.cable.label} → {pw}"
        return f"{self.cable.label} - Segment {self.pk}"

    def get_absolute_url(self):
        return reverse("plugins:netbox_pathways:cablesegment", args=[self.pk])

    @property
    def lashed_cables(self):
        """The dcim.Cable instances of every segment lashed with this one (excludes self.cable)."""
        return Cable.objects.filter(pathway_segments__in=self.lashed_with.all()).distinct()

    def save(self, *args, **kwargs):
        if self.sequence is None:
            max_seq = (CableSegment.objects.filter(cable=self.cable).aggregate(m=models.Max("sequence"))["m"]) or 0
            self.sequence = max_seq + 1
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.cable_id:
            from dcim.models import CableTermination

            a_exists = CableTermination.objects.filter(
                cable=self.cable,
                cable_end="A",
            ).exists()
            b_exists = CableTermination.objects.filter(
                cable=self.cable,
                cable_end="B",
            ).exists()
            if not (a_exists and b_exists):
                raise ValidationError(
                    {
                        "cable": "Cable must have both A and B terminations before routing.",
                    }
                )


class PlannedRoute(NetBoxModel):
    name = models.CharField(max_length=200)
    status = models.CharField(
        max_length=50,
        choices=PlannedRouteStatusChoices,
        default=PlannedRouteStatusChoices.STATUS_DRAFT,
    )
    start_structure = models.ForeignKey(
        Structure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planned_routes_from",
    )
    end_structure = models.ForeignKey(
        Structure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planned_routes_to",
    )
    start_location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planned_routes_from",
    )
    end_location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planned_routes_to",
    )
    pathway_ids = models.JSONField(
        default=list,
        help_text="Ordered list of pathway PKs defining the route",
    )
    constraints = models.JSONField(
        default=dict,
        blank=True,
        help_text="Snapshot of constraints used to generate this route",
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planned_routes",
    )
    cable = models.ForeignKey(
        Cable,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planned_routes",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        help_text="Original route this was split from",
    )
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_pathways:plannedroute", args=[self.pk])

    @property
    def start_endpoint(self):
        return self.start_structure or self.start_location

    @property
    def end_endpoint(self):
        return self.end_structure or self.end_location

    @property
    def hop_count(self):
        return len(self.pathway_ids)

    @property
    def total_length(self):
        if not self.pathway_ids:
            return 0
        lengths = Pathway.objects.filter(
            pk__in=self.pathway_ids,
        ).values_list("length", flat=True)
        return sum(v for v in lengths if v)

    def validate_route(self):
        """Check all pathway IDs still exist. Returns list of missing IDs."""
        existing = set(Pathway.objects.filter(pk__in=self.pathway_ids).values_list("pk", flat=True))
        return [pid for pid in self.pathway_ids if pid not in existing]

    def clean(self):
        super().clean()
        if self.start_structure and self.start_location:
            raise ValidationError("Set either start_structure or start_location, not both.")
        if not self.start_structure and not self.start_location:
            raise ValidationError("A start endpoint (structure or location) is required.")
        if self.end_structure and self.end_location:
            raise ValidationError("Set either end_structure or end_location, not both.")
        if not self.end_structure and not self.end_location:
            raise ValidationError("An end endpoint (structure or location) is required.")

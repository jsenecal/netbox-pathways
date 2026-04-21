from circuits.models import Circuit
from dcim.models import Cable, Location, Site
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.urls import reverse
from netbox.models import NetBoxModel
from tenancy.models import Tenant

from .choices import (
    AerialTypeChoices,
    BankFaceChoices,
    ConduitBankConfigChoices,
    ConduitMaterialChoices,
    EncasementTypeChoices,
    PathwayTypeChoices,
    StructureStatusChoices,
    StructureTypeChoices,
)
from .geo import get_srid

ENDPOINT_TOLERANCE = 1.0


class Structure(NetBoxModel):
    name = models.CharField(max_length=100, unique=True)
    status = models.CharField(
        max_length=50, choices=StructureStatusChoices,
        default=StructureStatusChoices.STATUS_ACTIVE,
    )
    structure_type = models.CharField(max_length=50, choices=StructureTypeChoices, blank=True)
    site = models.ForeignKey(
        Site, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pathways_structures',
    )
    location = models.GeometryField(
        srid=get_srid(),
        help_text="Geographic geometry (point for simple structures, polygon for footprints)",
    )
    elevation = models.FloatField(null=True, blank=True, help_text="Elevation in meters")
    height = models.FloatField(null=True, blank=True, help_text="Height in meters")
    width = models.FloatField(null=True, blank=True, help_text="Width in meters")
    length = models.FloatField(null=True, blank=True, help_text="Length in meters")
    depth = models.FloatField(null=True, blank=True, help_text="Depth in meters")
    installation_date = models.DateField(null=True, blank=True)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pathways_structures',
    )
    access_notes = models.TextField(blank=True, help_text="Access restrictions or requirements")
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['structure_type']),
            models.Index(fields=['site']),
            models.Index(fields=['status']),
        ]

    def get_status_color(self):
        return StructureStatusChoices.colors.get(self.status)

    @property
    def centroid(self):
        """Return the centroid point regardless of geometry type."""
        if self.location is None:
            return None
        if self.location.geom_type == 'Point':
            return self.location
        return self.location.centroid

    def __str__(self):
        if self.structure_type:
            return f"{self.name} ({self.get_structure_type_display()})"
        return self.name

    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:structure', args=[self.pk])


class SiteGeometry(NetBoxModel):
    """
    Links a NetBox Site to pathways infrastructure.

    Optionally associates a Structure (the Site IS this Structure), and
    provides a geometry field for the site boundary/footprint.  When a
    structure is linked and no explicit geometry is set, the geometry is
    copied from the structure on save.
    """
    site = models.OneToOneField(
        Site, on_delete=models.CASCADE, related_name='pathways_geometry',
    )
    structure = models.OneToOneField(
        'Structure', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='site_geometry',
        help_text="Structure that physically represents this site",
    )
    geometry = models.GeometryField(
        srid=get_srid(), null=True, blank=True,
        help_text="Site boundary or footprint — auto-populated from structure if blank",
    )
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ['site']
        verbose_name = 'Site Geometry'
        verbose_name_plural = 'Site Geometries'

    @property
    def effective_geometry(self):
        """Return explicit geometry, or fall back to linked structure's geometry."""
        if self.geometry:
            return self.geometry
        if self.structure_id and self.structure.location:
            return self.structure.location
        return None

    def __str__(self):
        return f"Geometry: {self.site.name}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:sitegeometry', args=[self.pk])

    def save(self, *args, **kwargs):
        if self.structure_id and not self.geometry:
            self.geometry = self.structure.location
        super().save(*args, **kwargs)


class CircuitGeometry(NetBoxModel):
    """
    Stores a provider-described route geometry for a native NetBox Circuit.

    The circuit itself is a black box — this just records the geographic path
    the provider says the circuit follows, for display on the infrastructure map.
    """
    circuit = models.OneToOneField(
        Circuit, on_delete=models.CASCADE, related_name='pathways_route',
    )
    path = models.LineStringField(
        srid=get_srid(),
        help_text="Provider-described route as a LineString",
    )
    provider_reference = models.CharField(
        max_length=200, blank=True,
        help_text="Provider's route/span ID or document reference",
    )
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ['circuit']
        verbose_name = 'Circuit Geometry'
        verbose_name_plural = 'Circuit Geometries'

    def __str__(self):
        return f"Route: {self.circuit.cid}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:circuitgeometry', args=[self.pk])


# ConduitBank is defined after Pathway (it's a Pathway subclass).


class Pathway(NetBoxModel):
    prerequisite_models = (
        'netbox_pathways.Structure',
    )

    label = models.CharField(max_length=100, blank=True)
    pathway_type = models.CharField(max_length=50, choices=PathwayTypeChoices, editable=False)
    path = models.LineStringField(srid=get_srid(), help_text="Geographic path")
    start_structure = models.ForeignKey(
        Structure, on_delete=models.PROTECT, null=True, blank=True, related_name='pathways_out',
    )
    end_structure = models.ForeignKey(
        Structure, on_delete=models.PROTECT, null=True, blank=True, related_name='pathways_in',
    )
    start_location = models.ForeignKey(
        Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='pathways_out',
    )
    end_location = models.ForeignKey(
        Location, on_delete=models.SET_NULL, null=True, blank=True, related_name='pathways_in',
    )
    tenant = models.ForeignKey(
        Tenant, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pathways_pathways',
    )
    length = models.FloatField(null=True, blank=True, help_text="Total length in meters")
    installation_date = models.DateField(null=True, blank=True)
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ['pk']
        indexes = [
            models.Index(fields=['pathway_type']),
            models.Index(fields=['start_structure', 'end_structure']),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pk = self.__dict__.get('id')

    @property
    def start_endpoint(self):
        return self.start_structure or self.start_location

    @property
    def end_endpoint(self):
        return self.end_structure or self.end_location

    def clean(self):
        super().clean()
        if not self.path:
            return
        self._validate_and_snap_endpoint('start')
        self._validate_and_snap_endpoint('end')

    def _validate_and_snap_endpoint(self, side):
        """Validate and snap one endpoint of self.path to the attached structure."""
        from django.contrib.gis.geos import LineString, Point

        structure = getattr(self, f'{side}_structure', None)
        if not structure or not structure.location:
            return

        coords = list(self.path.coords)
        idx = 0 if side == 'start' else -1
        endpoint = Point(coords[idx][0], coords[idx][1], srid=self.path.srid)
        geom = structure.location

        if geom.geom_type == 'Point':
            if endpoint.distance(geom) <= ENDPOINT_TOLERANCE:
                coords[idx] = (geom.x, geom.y)
            else:
                raise ValidationError({
                    'path': f"Path {side} point is too far from the {side} structure "
                            f"(must be within {ENDPOINT_TOLERANCE}m)."
                })
        else:
            # Polygon or other area geometry
            if geom.contains(endpoint) or geom.boundary.distance(endpoint) <= ENDPOINT_TOLERANCE:
                boundary = geom.boundary
                snap_point = boundary.interpolate(boundary.project(endpoint))
                coords[idx] = (snap_point.x, snap_point.y)
            else:
                raise ValidationError({
                    'path': f"Path {side} point is too far from the {side} structure "
                            f"(must be within {ENDPOINT_TOLERANCE}m of the boundary)."
                })

        self.path = LineString(coords, srid=self.path.srid)

    def __str__(self):
        return self.label or f'#{self.pk or self._pk}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:pathway', args=[self.pk])

    @property
    def map_visible(self):
        """Whether this pathway should be rendered as its own feature on the map.

        Returns False for pathways that are children of a container which owns the
        map representation (e.g. a conduit inside a bank, an innerduct inside a
        conduit).  The container is the feature that gets drawn; children are
        detail-level records shown in the sidebar / detail view.
        """
        return True

    @classmethod
    def map_queryset(cls, queryset=None):
        """Return a queryset filtered to only map-visible pathways.

        Excludes conduits that belong to a bank (the bank is drawn instead)
        and innerducts (drawn as part of their parent conduit's detail view).
        """
        if queryset is None:
            queryset = cls.objects.all()
        return queryset.exclude(
            pathway_type='innerduct',
        ).exclude(
            pathway_type='conduit',
            conduit__conduit_bank__isnull=False,
        )

    def save(self, *args, **kwargs):
        if not self.pathway_type:
            if isinstance(self, ConduitBank):
                self.pathway_type = 'conduit_bank'
            elif isinstance(self, Conduit):
                self.pathway_type = 'conduit'
            elif isinstance(self, AerialSpan):
                self.pathway_type = 'aerial'
            elif isinstance(self, DirectBuried):
                self.pathway_type = 'direct_buried'
            elif isinstance(self, Innerduct):
                self.pathway_type = 'innerduct'
        super().save(*args, **kwargs)
        self._pk = self.pk


class ConduitBank(Pathway):
    """
    An encased group of conduits sharing a physical route between two structures.
    The bank is the map-visible feature; individual conduits inside are detail records.
    """
    start_face = models.CharField(
        max_length=50, choices=BankFaceChoices, blank=True,
        help_text="Which face/wall of the start structure",
    )
    end_face = models.CharField(
        max_length=50, choices=BankFaceChoices, blank=True,
        help_text="Which face/wall of the end structure",
    )
    configuration = models.CharField(
        max_length=50, choices=ConduitBankConfigChoices, blank=True,
        help_text="Layout configuration (e.g., 2x2, 3x3) — leave blank if irregular",
    )
    total_conduits = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Designed conduit capacity of the bank (leave blank if unknown)",
    )
    encasement_type = models.CharField(max_length=50, choices=EncasementTypeChoices, blank=True)

    class Meta:
        verbose_name = "Conduit Bank"
        verbose_name_plural = "Conduit Banks"

    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:conduitbank', args=[self.pk])

    def save(self, *args, **kwargs):
        self.pathway_type = 'conduit_bank'
        super().save(*args, **kwargs)


class Conduit(Pathway):
    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:conduit', args=[self.pk])

    start_face = models.CharField(
        max_length=50, choices=BankFaceChoices, blank=True,
        help_text="Which face/wall of the start structure (for standalone conduits)",
    )
    end_face = models.CharField(
        max_length=50, choices=BankFaceChoices, blank=True,
        help_text="Which face/wall of the end structure (for standalone conduits)",
    )
    material = models.CharField(max_length=50, choices=ConduitMaterialChoices, blank=True)
    inner_diameter = models.FloatField(null=True, blank=True, help_text="Inner diameter in millimeters")
    outer_diameter = models.FloatField(null=True, blank=True, help_text="Outer diameter in millimeters")
    depth = models.FloatField(null=True, blank=True, help_text="Burial depth in meters")
    conduit_bank = models.ForeignKey(
        ConduitBank, on_delete=models.SET_NULL, null=True, blank=True, related_name='conduits',
    )
    bank_position = models.CharField(
        max_length=10, blank=True, help_text="Position in bank (e.g., A1, B2)",
    )
    start_junction = models.ForeignKey(
        'ConduitJunction', on_delete=models.SET_NULL, null=True, blank=True, related_name='conduits_from',
    )
    end_junction = models.ForeignKey(
        'ConduitJunction', on_delete=models.SET_NULL, null=True, blank=True, related_name='conduits_to',
    )

    @property
    def map_visible(self):
        return self.conduit_bank_id is None

    class Meta:
        verbose_name = "Conduit"
        verbose_name_plural = "Conduits"
        indexes = [
            models.Index(fields=['material']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['conduit_bank', 'bank_position'],
                name='unique_position_per_bank',
                condition=models.Q(conduit_bank__isnull=False, bank_position__gt=''),
            ),
        ]

    def clean(self):
        super().clean()  # Pathway.clean() handles structure endpoints
        start_options = sum(bool(x) for x in [self.start_structure, self.start_location, self.start_junction])
        end_options = sum(bool(x) for x in [self.end_structure, self.end_location, self.end_junction])

        if start_options == 0:
            raise ValidationError("Conduit must have a start point (structure, location, or junction)")
        if start_options > 1:
            raise ValidationError("Conduit start must be exactly one of: structure, location, or junction")
        if end_options == 0:
            raise ValidationError("Conduit must have an end point (structure, location, or junction)")
        if end_options > 1:
            raise ValidationError("Conduit end must be exactly one of: structure, location, or junction")

        # Validate/snap junction endpoints (structure endpoints handled by Pathway.clean)
        if self.path:
            self._validate_and_snap_junction('start')
            self._validate_and_snap_junction('end')

    def _validate_and_snap_junction(self, side):
        """Validate and snap one endpoint to the attached junction's location."""
        from django.contrib.gis.geos import LineString, Point

        junction = getattr(self, f'{side}_junction', None)
        if not junction:
            return
        junc_loc = junction.location
        if junc_loc is None:
            return

        coords = list(self.path.coords)
        idx = 0 if side == 'start' else -1
        endpoint = Point(coords[idx][0], coords[idx][1], srid=self.path.srid)

        if endpoint.distance(junc_loc) <= ENDPOINT_TOLERANCE:
            coords[idx] = (junc_loc.x, junc_loc.y)
            self.path = LineString(coords, srid=self.path.srid)
        else:
            raise ValidationError({
                'path': f"Path {side} point is too far from the {side} junction "
                        f"(must be within {ENDPOINT_TOLERANCE}m)."
            })

    def save(self, *args, **kwargs):
        self.pathway_type = 'conduit'
        super().save(*args, **kwargs)


class AerialSpan(Pathway):
    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:aerialspan', args=[self.pk])

    aerial_type = models.CharField(max_length=50, choices=AerialTypeChoices, blank=True)
    attachment_height = models.FloatField(null=True, blank=True, help_text="Attachment height in meters")
    sag = models.FloatField(null=True, blank=True, help_text="Cable sag in meters")
    messenger_size = models.CharField(max_length=50, blank=True, help_text="Messenger wire size/type")
    wind_loading = models.CharField(max_length=50, blank=True, help_text="Wind loading zone/rating")
    ice_loading = models.CharField(max_length=50, blank=True, help_text="Ice loading zone/rating")

    class Meta:
        verbose_name = "Aerial Span"
        verbose_name_plural = "Aerial Spans"
        indexes = [
            models.Index(fields=['aerial_type']),
        ]

    def save(self, *args, **kwargs):
        self.pathway_type = 'aerial'
        super().save(*args, **kwargs)


class DirectBuried(Pathway):
    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:directburied', args=[self.pk])

    burial_depth = models.FloatField(null=True, blank=True, help_text="Burial depth in meters")
    warning_tape = models.BooleanField(default=False, help_text="Warning tape installed above cable")
    tracer_wire = models.BooleanField(default=False, help_text="Tracer wire installed with cable")
    armor_type = models.CharField(max_length=100, blank=True, help_text="Cable armor type if applicable")

    class Meta:
        verbose_name = "Direct Buried"
        verbose_name_plural = "Direct Buried Paths"

    def save(self, *args, **kwargs):
        self.pathway_type = 'direct_buried'
        super().save(*args, **kwargs)


class Innerduct(Pathway):
    prerequisite_models = (
        'netbox_pathways.Conduit',
    )

    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:innerduct', args=[self.pk])

    parent_conduit = models.ForeignKey(Conduit, on_delete=models.CASCADE, related_name='innerducts')

    @property
    def map_visible(self):
        return False
    size = models.CharField(max_length=50, help_text='Innerduct size (e.g., 1.25", 32mm)')
    color = models.CharField(max_length=50, blank=True, help_text="Innerduct color for identification")
    position = models.CharField(max_length=50, blank=True, help_text="Position within parent conduit")

    class Meta:
        verbose_name = "Innerduct"
        verbose_name_plural = "Innerducts"

    def save(self, *args, **kwargs):
        self.pathway_type = 'innerduct'
        if self.parent_conduit_id:
            # Inherit start endpoint from parent if not explicitly set
            if not any([self.start_structure_id, self.start_location_id]):
                self.start_structure = self.parent_conduit.start_structure
                self.start_location = self.parent_conduit.start_location
            # Inherit end endpoint from parent if not explicitly set
            if not any([self.end_structure_id, self.end_location_id]):
                self.end_structure = self.parent_conduit.end_structure
                self.end_location = self.parent_conduit.end_location
        super().save(*args, **kwargs)


class ConduitJunction(NetBoxModel):
    prerequisite_models = (
        'netbox_pathways.Conduit',
    )

    label = models.CharField(max_length=100, blank=True)
    trunk_conduit = models.ForeignKey(
        Conduit, on_delete=models.CASCADE, related_name='junctions_on_trunk',
    )
    branch_conduit = models.ForeignKey(
        Conduit, on_delete=models.CASCADE, related_name='junction_as_branch',
    )
    towards_structure = models.ForeignKey(
        Structure, on_delete=models.PROTECT, help_text="Which end of trunk the junction faces",
    )
    position_on_trunk = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Position along trunk (0=start, 1=end)",
    )
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ['pk']
        constraints = [
            models.UniqueConstraint(
                fields=['trunk_conduit', 'position_on_trunk'],
                name='unique_junction_position_on_trunk',
            ),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pk = self.__dict__.get('id')

    def __str__(self):
        return self.label or f'#{self.pk or self._pk}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._pk = self.pk

    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:conduitjunction', args=[self.pk])

    def clean(self):
        super().clean()
        if self.trunk_conduit and self.towards_structure:
            trunk_structures = [
                s for s in [
                    self.trunk_conduit.start_structure,
                    self.trunk_conduit.end_structure,
                ] if s is not None
            ]
            if trunk_structures and self.towards_structure not in trunk_structures:
                raise ValidationError(
                    "towards_structure must be one of the trunk conduit's structure endpoints"
                )
            elif not trunk_structures:
                raise ValidationError(
                    "towards_structure cannot be set when the trunk conduit "
                    "has no structure endpoints (uses locations or junctions only)"
                )

    @property
    def location(self):
        if self.trunk_conduit and self.trunk_conduit.path:
            return self.trunk_conduit.path.interpolate_normalized(self.position_on_trunk)
        return None


class PathwayLocation(NetBoxModel):
    """
    Records that a pathway passes through a specific location or site along its length.
    Ordered waypoints between the start and end endpoints.
    """
    prerequisite_models = (
        'netbox_pathways.Pathway',
    )

    pathway = models.ForeignKey(
        Pathway, on_delete=models.CASCADE, related_name='waypoints',
    )
    site = models.ForeignKey(
        Site, on_delete=models.PROTECT, null=True, blank=True, related_name='pathway_waypoints',
    )
    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, null=True, blank=True, related_name='pathway_waypoints',
    )
    sequence = models.PositiveIntegerField(default=0, help_text="Order along the pathway")
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ['pathway', 'sequence']
        constraints = [
            models.UniqueConstraint(
                fields=['pathway', 'sequence'],
                name='unique_pathway_location_sequence',
            ),
        ]

    def __str__(self):
        point = self.location or self.site
        return f"{self.pathway} @ {point} (seq {self.sequence})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:pathwaylocation', args=[self.pk])

    def clean(self):
        super().clean()
        if not self.site and not self.location:
            raise ValidationError("At least one of site or location is required")


class CableSegment(NetBoxModel):
    prerequisite_models = (
        'netbox_pathways.Pathway',
    )

    cable = models.ForeignKey(Cable, on_delete=models.CASCADE, related_name='pathway_segments')
    pathway = models.ForeignKey(
        Pathway, on_delete=models.SET_NULL, null=True, blank=True, related_name='cable_segments',
    )
    sequence = models.PositiveIntegerField(
        null=True, blank=True, help_text="Order of segment in cable route (auto-assigned)",
    )
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ['cable', 'sequence']
        constraints = [
            models.UniqueConstraint(
                fields=['cable', 'sequence'],
                name='unique_cable_segment_sequence',
            ),
        ]

    def __str__(self):
        pw = self.pathway
        if pw:
            return f"{self.cable.label} → {pw}"
        return f"{self.cable.label} - Segment {self.pk}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:cablesegment', args=[self.pk])

    def save(self, *args, **kwargs):
        if self.sequence is None:
            max_seq = (
                CableSegment.objects
                .filter(cable=self.cable)
                .aggregate(m=models.Max('sequence'))['m']
            ) or 0
            self.sequence = max_seq + 1
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.cable_id:
            from dcim.models import CableTermination
            a_exists = CableTermination.objects.filter(
                cable=self.cable, cable_end='A',
            ).exists()
            b_exists = CableTermination.objects.filter(
                cable=self.cable, cable_end='B',
            ).exists()
            if not (a_exists and b_exists):
                raise ValidationError({
                    'cable': "Cable must have both A and B terminations before routing.",
                })


class SlackLoop(NetBoxModel):
    prerequisite_models = (
        'netbox_pathways.Structure',
    )

    cable = models.ForeignKey(Cable, on_delete=models.CASCADE, related_name='slack_loops')
    structure = models.ForeignKey(Structure, on_delete=models.CASCADE, related_name='slack_loops')
    pathway = models.ForeignKey(
        Pathway, on_delete=models.SET_NULL, null=True, blank=True, related_name='slack_loops',
        help_text="For aerial slack stored on a span near the structure",
    )
    length = models.FloatField(help_text="Length of slack in meters")
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ['cable', 'structure']

    def __str__(self):
        return f"{self.cable.label} — {self.length}m @ {self.structure.name}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:slackloop', args=[self.pk])

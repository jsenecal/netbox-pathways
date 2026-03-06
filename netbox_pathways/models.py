from dcim.models import Cable, Location, Site
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.urls import reverse
from netbox.models import NetBoxModel

from .choices import (
    AerialTypeChoices,
    ConduitBankConfigChoices,
    ConduitMaterialChoices,
    EncasementTypeChoices,
    PathwayTypeChoices,
    StructureTypeChoices,
)


class Structure(NetBoxModel):
    name = models.CharField(max_length=100, unique=True)
    structure_type = models.CharField(max_length=50, choices=StructureTypeChoices, blank=True)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='pathways_structures')
    location = models.PointField(srid=4326, help_text="Geographic location (WGS84)")
    elevation = models.FloatField(null=True, blank=True, help_text="Elevation in meters")
    installation_date = models.DateField(null=True, blank=True)
    owner = models.CharField(max_length=100, blank=True, help_text="Structure owner/operator")
    access_notes = models.TextField(blank=True, help_text="Access restrictions or requirements")
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['structure_type']),
            models.Index(fields=['site']),
        ]

    def __str__(self):
        if self.structure_type:
            return f"{self.name} ({self.get_structure_type_display()})"
        return self.name

    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:structure', args=[self.pk])


class ConduitBank(NetBoxModel):
    """
    A group of conduit openings on one side/wall of a structure (e.g., a manhole wall).
    Configuration can be irregular. Individual conduits each have their own destinations.
    """
    name = models.CharField(max_length=100, unique=True)
    structure = models.ForeignKey(
        Structure, on_delete=models.PROTECT, related_name='conduit_banks',
    )
    configuration = models.CharField(
        max_length=50, choices=ConduitBankConfigChoices, blank=True,
        help_text="Layout configuration (e.g., 2x2, 3x3) — leave blank if irregular",
    )
    total_conduits = models.PositiveIntegerField(help_text="Total number of conduit positions in bank")
    encasement_type = models.CharField(max_length=50, choices=EncasementTypeChoices, blank=True)
    installation_date = models.DateField(null=True, blank=True)
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['structure']),
        ]

    def __str__(self):
        return f"{self.name} @ {self.structure.name}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:conduitbank', args=[self.pk])


class Pathway(NetBoxModel):
    name = models.CharField(max_length=100, unique=True)
    pathway_type = models.CharField(max_length=50, choices=PathwayTypeChoices, editable=False)
    path = models.LineStringField(srid=4326, help_text="Geographic path")
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
    length = models.FloatField(null=True, blank=True, help_text="Total length in meters")
    installation_date = models.DateField(null=True, blank=True)
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['pathway_type']),
            models.Index(fields=['start_structure', 'end_structure']),
        ]

    @property
    def start_endpoint(self):
        return self.start_structure or self.start_location

    @property
    def end_endpoint(self):
        return self.end_structure or self.end_location

    def __str__(self):
        parts = [self.name]
        start = self.start_endpoint
        end = self.end_endpoint
        if start and end:
            parts.append(f"{start} \u2192 {end}")
        return ": ".join(parts)

    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:pathway', args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.pathway_type:
            if isinstance(self, Conduit):
                self.pathway_type = 'conduit'
            elif isinstance(self, AerialSpan):
                self.pathway_type = 'aerial'
            elif isinstance(self, DirectBuried):
                self.pathway_type = 'direct_buried'
            elif isinstance(self, Innerduct):
                self.pathway_type = 'innerduct'
        super().save(*args, **kwargs)


class Conduit(Pathway):
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

    class Meta:
        verbose_name = "Conduit"
        verbose_name_plural = "Conduits"
        constraints = [
            models.UniqueConstraint(
                fields=['conduit_bank', 'bank_position'],
                name='unique_position_per_bank',
                condition=models.Q(conduit_bank__isnull=False, bank_position__gt=''),
            ),
        ]

    def clean(self):
        super().clean()
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

    def save(self, *args, **kwargs):
        self.pathway_type = 'conduit'
        super().save(*args, **kwargs)


class AerialSpan(Pathway):
    aerial_type = models.CharField(max_length=50, choices=AerialTypeChoices, blank=True)
    attachment_height = models.FloatField(null=True, blank=True, help_text="Attachment height in meters")
    sag = models.FloatField(null=True, blank=True, help_text="Cable sag in meters")
    messenger_size = models.CharField(max_length=50, blank=True, help_text="Messenger wire size/type")
    wind_loading = models.CharField(max_length=50, blank=True, help_text="Wind loading zone/rating")
    ice_loading = models.CharField(max_length=50, blank=True, help_text="Ice loading zone/rating")

    class Meta:
        verbose_name = "Aerial Span"
        verbose_name_plural = "Aerial Spans"

    def save(self, *args, **kwargs):
        self.pathway_type = 'aerial'
        super().save(*args, **kwargs)


class DirectBuried(Pathway):
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
    parent_conduit = models.ForeignKey(Conduit, on_delete=models.CASCADE, related_name='innerducts')
    size = models.CharField(max_length=50, help_text='Innerduct size (e.g., 1.25", 32mm)')
    color = models.CharField(max_length=50, blank=True, help_text="Innerduct color for identification")
    position = models.CharField(max_length=50, blank=True, help_text="Position within parent conduit")

    class Meta:
        verbose_name = "Innerduct"
        verbose_name_plural = "Innerducts"

    def save(self, *args, **kwargs):
        self.pathway_type = 'innerduct'
        if self.parent_conduit and not any([
            self.start_structure_id, self.start_location_id,
        ]):
            self.start_structure = self.parent_conduit.start_structure
            self.end_structure = self.parent_conduit.end_structure
            self.start_location = self.parent_conduit.start_location
            self.end_location = self.parent_conduit.end_location
        super().save(*args, **kwargs)


class ConduitJunction(NetBoxModel):
    name = models.CharField(max_length=100, unique=True)
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
        ordering = ['name']
        unique_together = [['trunk_conduit', 'position_on_trunk']]

    def __str__(self):
        return f"{self.name}: {self.trunk_conduit.name} \u2192 {self.branch_conduit.name}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:conduitjunction', args=[self.pk])

    def clean(self):
        super().clean()
        if self.trunk_conduit and self.towards_structure:
            if self.towards_structure not in [
                self.trunk_conduit.start_structure,
                self.trunk_conduit.end_structure,
            ]:
                raise ValidationError(
                    "towards_structure must be one of the trunk conduit's endpoints"
                )

    @property
    def location(self):
        if self.trunk_conduit and self.trunk_conduit.path:
            return self.trunk_conduit.path.interpolate(self.position_on_trunk, normalized=True)
        return None


class PathwayLocation(NetBoxModel):
    """
    Records that a pathway passes through a specific location or site along its length.
    Ordered waypoints between the start and end endpoints.
    """
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
        unique_together = [['pathway', 'sequence']]

    def __str__(self):
        point = self.location or self.site
        return f"{self.pathway.name} @ {point} (seq {self.sequence})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:pathwaylocation', args=[self.pk])

    def clean(self):
        super().clean()
        if not self.site and not self.location:
            raise ValidationError("At least one of site or location is required")


class CableSegment(NetBoxModel):
    cable = models.ForeignKey(Cable, on_delete=models.CASCADE, related_name='pathway_segments')
    pathway = models.ForeignKey(
        Pathway, on_delete=models.SET_NULL, null=True, blank=True, related_name='cable_segments',
    )
    sequence = models.PositiveIntegerField(default=0, help_text="Order of segment in cable path")
    enter_point = models.PointField(srid=4326, null=True, blank=True, help_text="Entry point to pathway")
    exit_point = models.PointField(srid=4326, null=True, blank=True, help_text="Exit point from pathway")
    slack_loop_location = models.PointField(
        srid=4326, null=True, blank=True, help_text="Location of slack loop if present",
    )
    slack_length = models.FloatField(default=0, help_text="Length of slack in meters")
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ['cable', 'sequence']
        unique_together = [['cable', 'sequence']]

    def __str__(self):
        return f"{self.cable.label} - Segment {self.sequence}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_pathways:cablesegment', args=[self.pk])

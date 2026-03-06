from django.contrib.gis.db import models
from django.contrib.postgres.operations import CreateExtension
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.urls import reverse
from netbox.models import NetBoxModel
from dcim.models import Site, Cable, Device, FrontPort
from utilities.choices import ChoiceSet


class StructureTypeChoices(ChoiceSet):
    CHOICES = [
        ('pole', 'Pole', 'green'),
        ('manhole', 'Manhole', 'blue'),
        ('handhole', 'Handhole', 'cyan'),
        ('cabinet', 'Cabinet', 'orange'),
        ('vault', 'Vault', 'purple'),
        ('pedestal', 'Pedestal', 'yellow'),
        ('building_entrance', 'Building Entrance', 'red'),
        ('splice_closure', 'Splice Closure', 'brown'),
        ('tower', 'Tower', 'darkred'),
        ('roof', 'Rooftop', 'gray'),
    ]


class PathwayTypeChoices(ChoiceSet):
    CHOICES = [
        ('conduit', 'Conduit', 'brown'),
        ('aerial', 'Aerial Span', 'blue'),
        ('direct_buried', 'Direct Buried', 'gray'),
        ('innerduct', 'Innerduct', 'orange'),
        ('microduct', 'Microduct', 'purple'),
        ('tray', 'Cable Tray', 'green'),
        ('raceway', 'Raceway', 'cyan'),
        ('submarine', 'Submarine', 'navy'),
    ]


class ConduitMaterialChoices(ChoiceSet):
    CHOICES = [
        ('pvc', 'PVC', 'white'),
        ('hdpe', 'HDPE', 'black'),
        ('steel', 'Steel', 'gray'),
        ('concrete', 'Concrete', 'gray'),
        ('fiberglass', 'Fiberglass', 'yellow'),
    ]


class AerialTypeChoices(ChoiceSet):
    CHOICES = [
        ('messenger', 'Messenger Wire', 'black'),
        ('self_support', 'Self-Supporting', 'blue'),
        ('lashed', 'Lashed', 'green'),
        ('wrapped', 'Wrapped', 'orange'),
        ('adss', 'ADSS', 'purple'),
    ]


class ConduitBankConfigChoices(ChoiceSet):
    CHOICES = [
        ('1x2', '1x2 (2 conduits)', 'blue'),
        ('1x3', '1x3 (3 conduits)', 'green'),
        ('1x4', '1x4 (4 conduits)', 'orange'),
        ('2x2', '2x2 (4 conduits)', 'red'),
        ('2x3', '2x3 (6 conduits)', 'purple'),
        ('3x3', '3x3 (9 conduits)', 'brown'),
        ('3x4', '3x4 (12 conduits)', 'navy'),
        ('custom', 'Custom Configuration', 'gray'),
    ]


class EncasementTypeChoices(ChoiceSet):
    CHOICES = [
        ('concrete', 'Concrete Encased', 'gray'),
        ('direct_buried', 'Direct Buried', 'brown'),
        ('bore', 'Directional Bore', 'blue'),
        ('bridge_attachment', 'Bridge Attachment', 'green'),
        ('tunnel', 'Tunnel', 'black'),
    ]


class FiberTypeChoices(ChoiceSet):
    CHOICES = [
        ('sm', 'Single Mode', 'yellow'),
        ('mm_om1', 'Multimode OM1 (62.5µm)', 'orange'),
        ('mm_om2', 'Multimode OM2 (50µm)', 'orange'),
        ('mm_om3', 'Multimode OM3 (50µm)', 'aqua'),
        ('mm_om4', 'Multimode OM4 (50µm)', 'aqua'),
        ('mm_om5', 'Multimode OM5 (50µm)', 'lime'),
    ]


class CableTopologyChoices(ChoiceSet):
    CHOICES = [
        ('loose_tube', 'Loose Tube', 'blue'),
        ('tight_buffer', 'Tight Buffer', 'orange'),
        ('ribbon', 'Ribbon', 'purple'),
        ('armored', 'Armored', 'gray'),
        ('adss', 'ADSS (All-Dielectric Self-Supporting)', 'green'),
        ('opgw', 'OPGW (Optical Ground Wire)', 'black'),
        ('submarine', 'Submarine', 'navy'),
        ('microduct', 'Microduct Cable', 'cyan'),
    ]


class BufferColorChoices(ChoiceSet):
    """Standard fiber buffer tube colors per TIA-598"""
    CHOICES = [
        ('blue', 'Blue (1)', 'blue'),
        ('orange', 'Orange (2)', 'orange'),
        ('green', 'Green (3)', 'green'),
        ('brown', 'Brown (4)', 'brown'),
        ('slate', 'Slate (5)', 'slate'),
        ('white', 'White (6)', 'white'),
        ('red', 'Red (7)', 'red'),
        ('black', 'Black (8)', 'black'),
        ('yellow', 'Yellow (9)', 'yellow'),
        ('violet', 'Violet (10)', 'violet'),
        ('rose', 'Rose (11)', 'pink'),
        ('aqua', 'Aqua (12)', 'aqua'),
    ]


class FiberStructure(NetBoxModel):
    """
    Represents physical structures in the fiber network (poles, manholes, cabinets, etc.)
    """
    name = models.CharField(
        max_length=100,
        unique=True
    )
    structure_type = models.CharField(
        max_length=50,
        choices=StructureTypeChoices
    )
    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name='fiber_structures'
    )
    location = models.PointField(
        srid=4326,
        help_text="Geographic location (WGS84)"
    )
    elevation = models.FloatField(
        null=True,
        blank=True,
        help_text="Elevation in meters"
    )
    installation_date = models.DateField(
        null=True,
        blank=True
    )
    owner = models.CharField(
        max_length=100,
        blank=True,
        help_text="Structure owner/operator"
    )
    access_notes = models.TextField(
        blank=True,
        help_text="Access restrictions or requirements"
    )
    comments = models.TextField(
        blank=True
    )

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['structure_type']),
            models.Index(fields=['site']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_structure_type_display()})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_fiber:fiberstructure', args=[self.pk])


class ConduitBank(NetBoxModel):
    """
    Groups multiple conduits that share the same path between structures
    """
    name = models.CharField(
        max_length=100,
        unique=True
    )
    start_structure = models.ForeignKey(
        FiberStructure,
        on_delete=models.CASCADE,
        related_name='conduit_banks_out'
    )
    end_structure = models.ForeignKey(
        FiberStructure,
        on_delete=models.CASCADE,
        related_name='conduit_banks_in'
    )
    path = models.LineStringField(
        srid=4326,
        help_text="Geographic path of the conduit bank"
    )
    configuration = models.CharField(
        max_length=50,
        choices=ConduitBankConfigChoices,
        help_text="Layout configuration (e.g., 2x2, 3x3)"
    )
    total_conduits = models.PositiveIntegerField(
        help_text="Total number of conduits in bank"
    )
    encasement_type = models.CharField(
        max_length=50,
        choices=EncasementTypeChoices,
        blank=True
    )
    installation_date = models.DateField(
        null=True,
        blank=True
    )
    comments = models.TextField(
        blank=True
    )

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['start_structure', 'end_structure']),
        ]

    def __str__(self):
        return f"{self.name}: {self.start_structure.name} → {self.end_structure.name}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_fiber:conduitbank', args=[self.pk])


class FiberPathway(NetBoxModel):
    """
    Base class for all fiber pathway types (conduits, aerial spans, etc.)
    Uses model inheritance for specific pathway types
    """
    name = models.CharField(
        max_length=100,
        unique=True
    )
    pathway_type = models.CharField(
        max_length=50,
        choices=PathwayTypeChoices,
        editable=False  # Set by subclass
    )
    path = models.LineStringField(
        srid=4326,
        help_text="Geographic path"
    )
    start_structure = models.ForeignKey(
        FiberStructure,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='pathways_out'
    )
    end_structure = models.ForeignKey(
        FiberStructure,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='pathways_in'
    )
    length = models.FloatField(
        null=True,
        blank=True,
        help_text="Total length in meters"
    )
    cable_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of cables currently in pathway"
    )
    max_cable_count = models.PositiveIntegerField(
        default=1,
        help_text="Maximum number of cables"
    )
    installation_date = models.DateField(
        null=True,
        blank=True
    )
    comments = models.TextField(
        blank=True
    )

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['pathway_type']),
            models.Index(fields=['start_structure', 'end_structure']),
        ]

    def __str__(self):
        return f"{self.name}: {self.start_structure.name} → {self.end_structure.name}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_fiber:fiberpathway', args=[self.pk])

    @property
    def utilization_percentage(self):
        if self.max_cable_count == 0:
            return 0
        return (self.cable_count / self.max_cable_count) * 100

    def save(self, *args, **kwargs):
        # Set pathway_type based on the actual model class
        if not self.pathway_type:
            if isinstance(self, FiberConduit):
                self.pathway_type = 'conduit'
            elif isinstance(self, FiberAerialSpan):
                self.pathway_type = 'aerial'
            elif isinstance(self, FiberDirectBuried):
                self.pathway_type = 'direct_buried'
            elif isinstance(self, FiberInnerduct):
                self.pathway_type = 'innerduct'
        super().save(*args, **kwargs)


class FiberConduit(FiberPathway):
    """
    Underground conduit for fiber cables
    Can be standalone or part of a conduit bank
    Can connect to structures or junctions
    """
    material = models.CharField(
        max_length=50,
        choices=ConduitMaterialChoices,
        blank=True
    )
    inner_diameter = models.FloatField(
        null=True,
        blank=True,
        help_text="Inner diameter in millimeters"
    )
    outer_diameter = models.FloatField(
        null=True,
        blank=True,
        help_text="Outer diameter in millimeters"
    )
    depth = models.FloatField(
        null=True,
        blank=True,
        help_text="Burial depth in meters"
    )
    duct_count = models.PositiveIntegerField(
        default=1,
        help_text="Number of ducts in conduit bank"
    )
    
    # Conduit bank relationship
    conduit_bank = models.ForeignKey(
        ConduitBank,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conduits'
    )
    bank_position = models.CharField(
        max_length=10,
        blank=True,
        help_text="Position in bank (e.g., A1, B2)"
    )
    
    # Junction support - allow conduits to start/end at junctions
    start_junction = models.ForeignKey(
        'ConduitJunction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conduits_from'
    )
    end_junction = models.ForeignKey(
        'ConduitJunction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conduits_to'
    )

    class Meta:
        verbose_name = "Fiber Conduit"
        verbose_name_plural = "Fiber Conduits"

    def clean(self):
        super().clean()
        # Ensure conduit has valid endpoints
        start_valid = bool(self.start_structure or self.start_junction)
        end_valid = bool(self.end_structure or self.end_junction)
        
        if not start_valid:
            raise ValidationError("Conduit must have a start point (structure or junction)")
        if not end_valid:
            raise ValidationError("Conduit must have an end point (structure or junction)")
        
        # Can't have both structure and junction at same end
        if self.start_structure and self.start_junction:
            raise ValidationError("Cannot have both structure and junction at start")
        if self.end_structure and self.end_junction:
            raise ValidationError("Cannot have both structure and junction at end")

    def save(self, *args, **kwargs):
        self.pathway_type = 'conduit'
        # If part of a bank, inherit path from bank
        if self.conduit_bank and not self.path:
            self.path = self.conduit_bank.path
            if not self.start_structure_id and not self.start_junction_id:
                self.start_structure = self.conduit_bank.start_structure
            if not self.end_structure_id and not self.end_junction_id:
                self.end_structure = self.conduit_bank.end_structure
        super().save(*args, **kwargs)


class FiberAerialSpan(FiberPathway):
    """
    Aerial fiber span between poles/structures
    """
    aerial_type = models.CharField(
        max_length=50,
        choices=AerialTypeChoices
    )
    attachment_height = models.FloatField(
        null=True,
        blank=True,
        help_text="Attachment height in meters"
    )
    sag = models.FloatField(
        null=True,
        blank=True,
        help_text="Cable sag in meters"
    )
    messenger_size = models.CharField(
        max_length=50,
        blank=True,
        help_text="Messenger wire size/type"
    )
    wind_loading = models.CharField(
        max_length=50,
        blank=True,
        help_text="Wind loading zone/rating"
    )
    ice_loading = models.CharField(
        max_length=50,
        blank=True,
        help_text="Ice loading zone/rating"
    )

    class Meta:
        verbose_name = "Fiber Aerial Span"
        verbose_name_plural = "Fiber Aerial Spans"

    def save(self, *args, **kwargs):
        self.pathway_type = 'aerial'
        super().save(*args, **kwargs)


class FiberDirectBuried(FiberPathway):
    """
    Direct buried fiber cable path
    """
    burial_depth = models.FloatField(
        null=True,
        blank=True,
        help_text="Burial depth in meters"
    )
    warning_tape = models.BooleanField(
        default=False,
        help_text="Warning tape installed above cable"
    )
    tracer_wire = models.BooleanField(
        default=False,
        help_text="Tracer wire installed with cable"
    )
    armor_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Cable armor type if applicable"
    )

    class Meta:
        verbose_name = "Fiber Direct Buried"
        verbose_name_plural = "Fiber Direct Buried Paths"

    def save(self, *args, **kwargs):
        self.pathway_type = 'direct_buried'
        super().save(*args, **kwargs)


class FiberInnerduct(FiberPathway):
    """
    Innerduct or microduct within a larger conduit
    """
    parent_conduit = models.ForeignKey(
        FiberConduit,
        on_delete=models.CASCADE,
        related_name='innerducts'
    )
    size = models.CharField(
        max_length=50,
        help_text="Innerduct size (e.g., 1.25\", 32mm)"
    )
    color = models.CharField(
        max_length=50,
        blank=True,
        help_text="Innerduct color for identification"
    )
    position = models.CharField(
        max_length=50,
        blank=True,
        help_text="Position within parent conduit"
    )

    class Meta:
        verbose_name = "Fiber Innerduct"
        verbose_name_plural = "Fiber Innerducts"

    def save(self, *args, **kwargs):
        self.pathway_type = 'innerduct'
        # Inherit start/end structures from parent conduit if not set
        if self.parent_conduit and not self.start_structure_id:
            self.start_structure = self.parent_conduit.start_structure
            self.end_structure = self.parent_conduit.end_structure
        super().save(*args, **kwargs)


class FiberSplice(NetBoxModel):
    """
    Represents splice points and enclosures
    """
    name = models.CharField(
        max_length=100,
        unique=True
    )
    structure = models.ForeignKey(
        FiberStructure,
        on_delete=models.CASCADE,
        related_name='splices'
    )
    enclosure_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Type of splice enclosure"
    )
    fiber_count = models.PositiveIntegerField(
        default=0,
        help_text="Total fiber count in splice"
    )
    installation_date = models.DateField(
        null=True,
        blank=True
    )
    comments = models.TextField(
        blank=True
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} at {self.structure.name}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_fiber:fibersplice', args=[self.pk])


class ConduitJunction(NetBoxModel):
    """
    Represents a Y-junction where a branch conduit connects to a trunk conduit
    The branch connects mid-span on the trunk, creating a Y-shape
    """
    name = models.CharField(
        max_length=100,
        unique=True
    )
    
    # The main conduit that continues through
    trunk_conduit = models.ForeignKey(
        FiberConduit,
        on_delete=models.CASCADE,
        related_name='junctions_on_trunk'
    )
    
    # The conduit that branches off
    branch_conduit = models.ForeignKey(
        FiberConduit,
        on_delete=models.CASCADE,
        related_name='junction_as_branch'
    )
    
    # Which structure the junction is oriented towards on the trunk
    towards_structure = models.ForeignKey(
        FiberStructure,
        on_delete=models.CASCADE,
        help_text="Which end of trunk the junction faces"
    )
    
    # Where along the trunk (0.0 = start, 1.0 = end)
    position_on_trunk = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Position along trunk (0=start, 1=end)"
    )
    
    comments = models.TextField(
        blank=True
    )
    
    class Meta:
        ordering = ['name']
        unique_together = [['trunk_conduit', 'position_on_trunk']]
    
    def __str__(self):
        return f"{self.name}: {self.trunk_conduit.name} → {self.branch_conduit.name}"
    
    def get_absolute_url(self):
        return reverse('plugins:netbox_fiber:conduitjunction', args=[self.pk])
    
    def clean(self):
        super().clean()
        if self.trunk_conduit and self.towards_structure:
            # Ensure towards_structure is one of trunk's endpoints
            if self.towards_structure not in [self.trunk_conduit.start_structure, 
                                              self.trunk_conduit.end_structure]:
                raise ValidationError(
                    "towards_structure must be one of the trunk conduit's endpoints"
                )
    
    @property
    def location(self):
        """Calculate junction location from trunk path and position"""
        if self.trunk_conduit and self.trunk_conduit.path:
            # Get point at position along trunk's LineString
            return self.trunk_conduit.path.interpolate(
                self.position_on_trunk,
                normalized=True
            )
        return None


class FiberCable(NetBoxModel):
    """
    Supplements NetBox Cable with fiber-specific information
    One-to-one relationship with dcim.Cable
    """
    cable = models.OneToOneField(
        Cable,
        on_delete=models.CASCADE,
        related_name='fiber_cable'
    )
    manufacturer = models.CharField(
        max_length=100,
        blank=True
    )
    part_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Manufacturer part number"
    )
    fiber_type = models.CharField(
        max_length=50,
        choices=FiberTypeChoices
    )
    topology = models.CharField(
        max_length=50,
        choices=CableTopologyChoices
    )
    fiber_count = models.PositiveIntegerField(
        help_text="Total number of fibers in cable"
    )
    buffer_count = models.PositiveIntegerField(
        default=1,
        help_text="Number of buffer tubes or ribbons"
    )
    fibers_per_buffer = models.PositiveIntegerField(
        default=12,
        help_text="Number of fibers per buffer tube/ribbon"
    )
    jacket_color = models.CharField(
        max_length=50,
        blank=True,
        help_text="Cable jacket color"
    )
    print_legend = models.CharField(
        max_length=200,
        blank=True,
        help_text="Text printed on cable jacket"
    )
    serial_number = models.CharField(
        max_length=100,
        blank=True,
        unique=True,
        null=True
    )
    installation_date = models.DateField(
        null=True,
        blank=True
    )
    test_date = models.DateField(
        null=True,
        blank=True,
        help_text="Last OTDR test date"
    )
    comments = models.TextField(
        blank=True
    )

    class Meta:
        ordering = ['cable__label']

    def __str__(self):
        return f"{self.cable.label} ({self.fiber_count} fibers)"

    def get_absolute_url(self):
        return reverse('plugins:netbox_fiber:fibercable', args=[self.pk])
    
    def get_fiber_color(self, fiber_number):
        """Get standard TIA-598 color for fiber number"""
        colors = ['blue', 'orange', 'green', 'brown', 'slate', 'white',
                 'red', 'black', 'yellow', 'violet', 'rose', 'aqua']
        return colors[(fiber_number - 1) % 12]


class SpliceConnection(NetBoxModel):
    """
    Represents fiber splices between front ports within the same device
    Used for splice closures and patch panels
    """
    device = models.ForeignKey(
        'dcim.Device',
        on_delete=models.CASCADE,
        related_name='splice_connections'
    )
    a_port = models.ForeignKey(
        'dcim.FrontPort',
        on_delete=models.CASCADE,
        related_name='splice_a_connections'
    )
    b_port = models.ForeignKey(
        'dcim.FrontPort',
        on_delete=models.CASCADE,
        related_name='splice_b_connections'
    )
    splice_type = models.CharField(
        max_length=50,
        choices=[
            ('fusion', 'Fusion Splice'),
            ('mechanical', 'Mechanical Splice'),
            ('pigtail', 'Pigtail'),
            ('patch', 'Patch'),
        ],
        default='fusion'
    )
    loss = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Splice loss in dB"
    )
    created = models.DateTimeField(
        auto_now_add=True
    )
    comments = models.TextField(
        blank=True
    )

    class Meta:
        ordering = ['device', 'a_port', 'b_port']
        unique_together = [['a_port', 'b_port']]

    def __str__(self):
        return f"{self.device.name}: {self.a_port.name} ↔ {self.b_port.name}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_fiber:spliceconnection', args=[self.pk])

    def clean(self):
        super().clean()
        if self.a_port and self.b_port:
            # Ensure both ports belong to the same device
            if self.a_port.device != self.b_port.device:
                raise ValidationError("Both ports must belong to the same device")
            if self.a_port.device != self.device:
                raise ValidationError("Ports must belong to the specified device")
            # Prevent self-splice
            if self.a_port == self.b_port:
                raise ValidationError("Cannot splice a port to itself")


class FiberCableSegment(NetBoxModel):
    """
    Links NetBox cables to pathways and geographic paths
    """
    cable = models.ForeignKey(
        Cable,
        on_delete=models.CASCADE,
        related_name='fiber_segments'
    )
    pathway = models.ForeignKey(
        FiberPathway,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cable_segments'
    )
    sequence = models.PositiveIntegerField(
        default=0,
        help_text="Order of segment in cable path"
    )
    enter_point = models.PointField(
        srid=4326,
        null=True,
        blank=True,
        help_text="Entry point to pathway"
    )
    exit_point = models.PointField(
        srid=4326,
        null=True,
        blank=True,
        help_text="Exit point from pathway"
    )
    slack_loop_location = models.PointField(
        srid=4326,
        null=True,
        blank=True,
        help_text="Location of slack loop if present"
    )
    slack_length = models.FloatField(
        default=0,
        help_text="Length of slack in meters"
    )
    comments = models.TextField(
        blank=True
    )

    class Meta:
        ordering = ['cable', 'sequence']
        unique_together = [['cable', 'sequence']]

    def __str__(self):
        return f"{self.cable.label} - Segment {self.sequence}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_fiber:fibercablesegment', args=[self.pk])
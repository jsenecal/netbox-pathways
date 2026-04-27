from utilities.choices import ChoiceSet


class StructureStatusChoices(ChoiceSet):
    key = "Structure.status"

    STATUS_PLANNED = "planned"
    STATUS_ACTIVE = "active"
    STATUS_CONSTRUCTION = "construction"
    STATUS_DECOMMISSIONING = "decommissioning"
    STATUS_RETIRED = "retired"

    CHOICES = [
        (STATUS_PLANNED, "Planned", "cyan"),
        (STATUS_ACTIVE, "Active", "green"),
        (STATUS_CONSTRUCTION, "Under Construction", "blue"),
        (STATUS_DECOMMISSIONING, "Decommissioning", "yellow"),
        (STATUS_RETIRED, "Retired", "red"),
    ]


class StructureTypeChoices(ChoiceSet):
    CHOICES = [
        ("pole", "Pole", "green"),
        ("manhole", "Manhole", "blue"),
        ("handhole", "Handhole", "cyan"),
        ("cabinet", "Cabinet", "orange"),
        ("vault", "Vault", "purple"),
        ("pedestal", "Pedestal", "yellow"),
        ("building_entrance", "Building Entrance", "red"),
        ("splice_closure", "Splice Closure", "brown"),
        ("tower", "Tower", "darkred"),
        ("roof", "Rooftop", "gray"),
        ("equipment_room", "Equipment Room", "teal"),
        ("telecom_closet", "Telecom Closet", "indigo"),
        ("riser_room", "Riser Room", "pink"),
    ]


class PathwayTypeChoices(ChoiceSet):
    CHOICES = [
        ("conduit_bank", "Conduit Bank", "darkbrown"),
        ("conduit", "Conduit", "brown"),
        ("aerial", "Aerial Span", "blue"),
        ("direct_buried", "Direct Buried", "gray"),
        ("innerduct", "Innerduct", "orange"),
        ("microduct", "Microduct", "purple"),
        ("tray", "Cable Tray", "green"),
        ("raceway", "Raceway", "cyan"),
        ("submarine", "Submarine", "navy"),
    ]


class ConduitMaterialChoices(ChoiceSet):
    CHOICES = [
        ("pvc", "PVC", "white"),
        ("hdpe", "HDPE", "black"),
        ("steel", "Steel", "gray"),
        ("concrete", "Concrete", "gray"),
        ("fiberglass", "Fiberglass", "yellow"),
    ]


class AerialTypeChoices(ChoiceSet):
    CHOICES = [
        ("messenger", "Messenger Wire", "black"),
        ("self_support", "Self-Supporting", "blue"),
        ("lashed", "Lashed", "green"),
        ("wrapped", "Wrapped", "orange"),
        ("adss", "ADSS", "purple"),
    ]


class ConduitBankConfigChoices(ChoiceSet):
    CHOICES = [
        ("1x2", "1x2 (2 conduits)", "blue"),
        ("1x3", "1x3 (3 conduits)", "green"),
        ("1x4", "1x4 (4 conduits)", "orange"),
        ("2x2", "2x2 (4 conduits)", "red"),
        ("2x3", "2x3 (6 conduits)", "purple"),
        ("3x3", "3x3 (9 conduits)", "brown"),
        ("3x4", "3x4 (12 conduits)", "navy"),
        ("custom", "Custom Configuration", "gray"),
    ]


class BankFaceChoices(ChoiceSet):
    CHOICES = [
        ("north", "North", "blue"),
        ("south", "South", "red"),
        ("east", "East", "green"),
        ("west", "West", "orange"),
        ("other", "Other", "gray"),
    ]


class EncasementTypeChoices(ChoiceSet):
    CHOICES = [
        ("concrete", "Concrete Encased", "gray"),
        ("direct_buried", "Direct Buried", "brown"),
        ("bore", "Directional Bore", "blue"),
        ("bridge_attachment", "Bridge Attachment", "green"),
        ("tunnel", "Tunnel", "black"),
    ]


class PlannedRouteStatusChoices(ChoiceSet):
    key = "PlannedRoute.status"

    STATUS_DRAFT = "draft"
    STATUS_APPROVED = "approved"
    STATUS_ASSIGNED = "assigned"
    STATUS_SPLIT = "split"
    STATUS_ARCHIVED = "archived"

    CHOICES = [
        (STATUS_DRAFT, "Draft", "blue"),
        (STATUS_APPROVED, "Approved", "green"),
        (STATUS_ASSIGNED, "Assigned", "cyan"),
        (STATUS_SPLIT, "Split", "purple"),
        (STATUS_ARCHIVED, "Archived", "gray"),
    ]

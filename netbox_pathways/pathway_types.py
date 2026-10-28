"""Per-type metadata for pathways.

The single source of truth for what each ``pathway_type`` means: which
type-specific model fields apply, which pathway types it may sit inside,
whether it is drawn on the map, and how its geometry and endpoints behave.
The model, forms, serializers, filtersets, map and legend all read this
module instead of keeping their own per-type tables.

Pure data with no Django imports, so it can be loaded from anywhere
(including migrations) without app-registry ordering concerns.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PathwayTypeSpec:
    """What a single pathway type allows and how it behaves."""

    # Type-specific model fields that apply to this type.
    fields: tuple[str, ...]
    # pathway_type values this type may have as its parent.
    parents: frozenset[str] = frozenset()
    # True when a pathway of this type cannot exist without a parent.
    parent_required: bool = False
    # Drawn on the map when top-level (no parent).
    drawn: bool = False
    # Geometry is built from the endpoints rather than drawn by the user.
    derives_geometry: bool = False
    # Kinds of object a start/end endpoint may reference.
    endpoint_kinds: tuple[str, ...] = ("structure", "location")


PATHWAY_TYPES: dict[str, PathwayTypeSpec] = {
    "conduit_bank": PathwayTypeSpec(
        fields=(
            "start_face",
            "end_face",
            "configuration",
            "total_conduits",
            "height",
            "width",
            "encasement_type",
        ),
        drawn=True,
    ),
    "conduit": PathwayTypeSpec(
        fields=(
            "start_face",
            "end_face",
            "material",
            "inner_diameter",
            "outer_diameter",
            "depth",
            "position",
            "start_junction",
            "end_junction",
        ),
        parents=frozenset({"conduit_bank", "raceway"}),
        drawn=True,
        endpoint_kinds=("structure", "location", "junction"),
    ),
    "aerial": PathwayTypeSpec(
        fields=(
            "aerial_type",
            "start_attachment_height",
            "end_attachment_height",
            "sag",
            "messenger_size",
            "wind_loading",
            "ice_loading",
        ),
        drawn=True,
        derives_geometry=True,
    ),
    "direct_buried": PathwayTypeSpec(
        fields=("burial_depth", "warning_tape", "tracer_wire", "armor_type"),
        drawn=True,
    ),
    "innerduct": PathwayTypeSpec(
        fields=("size", "color", "position"),
        parents=frozenset({"conduit", "innerduct", "direct_buried", "tray"}),
        parent_required=True,
    ),
    "tray": PathwayTypeSpec(
        fields=(),
        parents=frozenset({"raceway"}),
    ),
    "raceway": PathwayTypeSpec(fields=()),
    "submarine": PathwayTypeSpec(fields=(), drawn=True),
}

TYPE_SPECIFIC_FIELDS: frozenset[str] = frozenset(f for s in PATHWAY_TYPES.values() for f in s.fields)

DRAWN_TYPES: frozenset[str] = frozenset(t for t, s in PATHWAY_TYPES.items() if s.drawn)


def spec(pathway_type: str) -> PathwayTypeSpec:
    """Return the spec for ``pathway_type``; raises KeyError if unknown."""
    return PATHWAY_TYPES[pathway_type]


def allowed_child_types(pathway_type: str) -> frozenset[str]:
    """Return the pathway types that may have ``pathway_type`` as their parent.

    An unknown or blank type contains nothing rather than raising: the upgrade
    leaves some pathways untyped for the operator to retype, and their detail
    page asks this question before they have been fixed.
    """
    return frozenset(t for t, s in PATHWAY_TYPES.items() if pathway_type in s.parents)


def inapplicable_fields(pathway_type: str) -> frozenset[str]:
    """Return the type-specific fields that do not apply to ``pathway_type``."""
    return TYPE_SPECIFIC_FIELDS - frozenset(spec(pathway_type).fields)

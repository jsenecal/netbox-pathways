"""Data steps of the upgrade from per-type pathway tables to one pathway table.

Pathways used to be a base table plus five multi-table-inheritance children
(conduit bank, conduit, aerial span, direct buried, innerduct). The flatten
migrations call these helpers with the historical app registry, so they are
written against `apps.get_model()` and never import the live models.

Migration 0028 renames every child column that also exists on the flattened
pathway to `legacy_<name>` (an MTI child may not shadow a parent field), adds
the flattened columns, and the copy below moves the values across.
"""

# Former child model name -> the pathway_type its rows carry.
LEGACY_SUBTYPES: dict[str, str] = {
    "conduitbank": "conduit_bank",
    "conduit": "conduit",
    "aerialspan": "aerial",
    "directburied": "direct_buried",
    "innerduct": "innerduct",
}

# Child columns that move to a pathway column of the same name; on the child
# tables they are renamed to legacy_<name> while both exist.
LEGACY_RENAMED_FIELDS: dict[str, tuple[str, ...]] = {
    "conduitbank": (
        "start_face",
        "end_face",
        "configuration",
        "total_conduits",
        "height",
        "width",
        "encasement_type",
    ),
    "conduit": (
        "start_face",
        "end_face",
        "material",
        "inner_diameter",
        "outer_diameter",
        "depth",
        "start_junction",
        "end_junction",
    ),
    "aerialspan": (
        "aerial_type",
        "start_attachment_height",
        "end_attachment_height",
        "sag",
        "messenger_size",
        "wind_loading",
        "ice_loading",
    ),
    "directburied": ("burial_depth", "warning_tape", "tracer_wire", "armor_type"),
    "innerduct": ("size", "color", "position"),
}

# Child columns that move to a differently named pathway column.
LEGACY_MOVED_FIELDS: dict[str, dict[str, str]] = {
    "conduit": {"conduit_bank": "parent", "bank_position": "position"},
    "innerduct": {"parent_conduit": "parent"},
}

# The only parent each former subtype could have, by pathway type.
LEGACY_PARENT_TYPES: dict[str, str] = {"conduit": "conduit_bank", "innerduct": "conduit"}

BATCH_SIZE = 1000


def _column_map(legacy_model, pathway_model, model_name):
    """{legacy attname: pathway attname} for one former child model."""
    pairs = {f"legacy_{name}": name for name in LEGACY_RENAMED_FIELDS[model_name]}
    pairs.update(LEGACY_MOVED_FIELDS.get(model_name, {}))
    return {
        legacy_model._meta.get_field(old).attname: pathway_model._meta.get_field(new).attname
        for old, new in pairs.items()
    }


def copy_subtype_rows(apps, schema_editor):
    """Copy every child-table row onto its pathway row.

    Sets the type-specific columns, `parent` (from the bank of a conduit or
    the conduit of an innerduct), `position` and `pathway_type`. Existing
    rows are copied as they are, without validation.
    """
    Pathway = apps.get_model("netbox_pathways", "Pathway")
    for model_name, pathway_type in LEGACY_SUBTYPES.items():
        legacy = apps.get_model("netbox_pathways", model_name)
        columns = _column_map(legacy, Pathway, model_name)
        batch = []
        for row in legacy.objects.values("pk", *columns).iterator(chunk_size=BATCH_SIZE):
            values = {new: row[old] for old, new in columns.items()}
            batch.append(Pathway(pk=row["pk"], pathway_type=pathway_type, **values))
        Pathway.objects.bulk_update(batch, ["pathway_type", *columns.values()], batch_size=BATCH_SIZE)


def uncopy_subtype_rows(apps, schema_editor):
    """Reverse of copy_subtype_rows(): rebuild the child-table rows.

    Refuses when a pathway has a parent the child tables cannot express
    (anything but a conduit in a bank or an innerduct in a conduit), rather
    than silently dropping it.
    """
    Pathway = apps.get_model("netbox_pathways", "Pathway")
    unrepresentable = Pathway.objects.filter(parent__isnull=False)
    for child_type, parent_type in LEGACY_PARENT_TYPES.items():
        unrepresentable = unrepresentable.exclude(pathway_type=child_type, parent__pathway_type=parent_type)
    stranded = list(unrepresentable.values_list("pk", flat=True)[:20])
    if stranded:
        raise RuntimeError(
            "Cannot reverse the pathway flatten: pathways "
            f"{', '.join(map(str, stranded))} have a parent the per-type tables cannot represent."
        )
    for model_name, pathway_type in LEGACY_SUBTYPES.items():
        legacy = apps.get_model("netbox_pathways", model_name)
        columns = _column_map(legacy, Pathway, model_name)
        rows = Pathway.objects.filter(pathway_type=pathway_type).values("pk", *set(columns.values()))
        for row in rows.iterator(chunk_size=BATCH_SIZE):
            values = {old: row[new] for old, new in columns.items()}
            # raw=True writes only the child table; the pathway row exists.
            legacy(pathway_ptr_id=row["pk"], **values).save_base(raw=True)


def delete_microducts(apps, schema_editor):
    """Delete pathways of the retired `microduct` type; return how many.

    Cable segments routed through them keep the segment with no pathway
    (CableSegment.pathway is SET_NULL). The count is printed so the
    operator sees it in the migrate output.
    """
    Pathway = apps.get_model("netbox_pathways", "Pathway")
    microducts = Pathway.objects.filter(pathway_type="microduct")
    count = microducts.count()
    if count:
        microducts.delete()
    print(f"\n  netbox_pathways: deleted {count} pathway(s) of the retired 'microduct' type.")
    return count

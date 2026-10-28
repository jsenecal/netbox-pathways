"""Data steps of the upgrade from per-type pathway tables to one pathway table.

Pathways used to be a base table plus five multi-table-inheritance children
(conduit bank, conduit, aerial span, direct buried, innerduct). The flatten
migrations call these helpers with the historical app registry, so they are
written against `apps.get_model()` and never import the live models.

Migration 0028 renames every child column that also exists on the flattened
pathway to `legacy_<name>` (an MTI child may not shadow a parent field), adds
the flattened columns, and the copy below moves the values across.
"""

import json

from django.core.exceptions import FieldDoesNotExist
from django.db import IntegrityError, transaction

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

# Types migration 0030 constrains to always have a parent (frozen here, like
# the constraint itself, so later rule changes do not alter this upgrade).
PARENT_REQUIRED_TYPES: tuple[str, ...] = ("innerduct",)

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


def untype_parentless_rows(apps, schema_editor):
    """Clear the type of pathways that would break the parent constraint; return their pks.

    The 0.4.x generic pathway endpoint stored a bare pathway row with no
    subtype row and accepted any `pathway_type`. Such a row typed
    `innerduct` has no parent conduit to copy, so it would fail the
    `pathway_parent_required` constraint added next and abort the upgrade.
    The row is kept, with its waypoints and cable segments, and only its
    type is cleared: a blank type satisfies every constraint and fails
    full_clean() on the next edit, so the user picks a type then. The pks
    are printed so the operator can find and retype them.

    Rows that already had a blank type are left alone for the same reason.
    """
    Pathway = apps.get_model("netbox_pathways", "Pathway")
    orphans = Pathway.objects.filter(pathway_type__in=PARENT_REQUIRED_TYPES, parent__isnull=True)
    pks = list(orphans.order_by("pk").values_list("pk", flat=True))
    if pks:
        Pathway.objects.filter(pk__in=pks).update(pathway_type="")
        print(
            f"\n  netbox_pathways: cleared the type of {len(pks)} {'/'.join(PARENT_REQUIRED_TYPES)} "
            f"pathway(s) with no parent; set a type on each: {', '.join(map(str, pks))}."
        )
    return pks


# --- Retiring the subtype content types -------------------------------------

# Legacy subtype field and relation names -> their name on the flattened
# pathway. The reverse accessors are included because a bank's conduits and
# a conduit's innerducts are now simply its children.
CONSTRAINT_RENAMES: dict[str, str] = {
    "conduit_bank": "parent",
    "conduit_bank_id": "parent_id",
    "parent_conduit": "parent",
    "parent_conduit_id": "parent_id",
    "bank_position": "position",
    "path": "geometry",
    "conduits": "children",
    "innerducts": "children",
}

# The MTI parent link of every former subtype. On the flattened model it is
# the row itself: `pathway_ptr` alone means `id`, and a field reached through
# it (`pathway_ptr__label`) is a field of the pathway.
PARENT_LINK_NAMES = ("pathway_ptr", "pathway_ptr_id")

CONTENT_TYPE_MODELS = frozenset({"contenttypes.contenttype", "core.objecttype"})

# Content-type references the generic repoint leaves alone: object
# permissions are converted on their own (their constraints need scoping),
# and Django's per-model auth permissions belong to the retired models and
# go with their content types.
REPOINT_SKIPPED = frozenset({("users.objectpermission", "object_types"), ("auth.permission", "content_type")})

PATHWAY_LABEL = "netbox_pathways.pathway"
PERMISSION_SUFFIX = " (pathways)"


class UntranslatableConstraint(Exception):  # noqa: N818 -- named by the upgrade interface
    """An object permission constraint that cannot be expressed on the flattened pathway."""


def _is_pathway(model):
    return model is not None and model._meta.label_lower == PATHWAY_LABEL


def _get_field(model, name):
    if name == "pk":
        return model._meta.pk
    try:
        return model._meta.get_field(name)
    except FieldDoesNotExist:
        return None


def _rewrite_key(key, pathway_model):
    """Rename the legacy segments of one constraint lookup and check it resolves.

    Every segment until the first non-relation field must be a field (or
    `pk`) of the model reached so far; renames apply wherever that model is
    the pathway. After a field, one lookup or transform it supports ends the
    check, and what follows is kept as written.
    """
    segments = key.split("__")
    out = []
    model, field = pathway_model, None
    index = 0
    while index < len(segments):
        segment = segments[index]
        if model is not None:
            if _is_pathway(model) and segment in PARENT_LINK_NAMES:
                following = segments[index + 1] if index + 1 < len(segments) else None
                if segment == "pathway_ptr" and following and _get_field(model, following):
                    index += 1
                    continue
                segment = "id"
            elif _is_pathway(model):
                segment = CONSTRAINT_RENAMES.get(segment, segment)
            found = _get_field(model, segment)
            if found is not None:
                out.append(segment)
                field = found
                model = found.related_model if found.is_relation else None
                index += 1
                continue
        if field is not None and (field.get_lookup(segment) or field.get_transform(segment)):
            return "__".join([*out, *segments[index:]])
        raise UntranslatableConstraint(f"{key!r} does not resolve on the flattened pathway")
    return "__".join(out)


def _scope_to_types(alternative, pathway_types, pathway_model):
    """One constraint dict with keys rewritten and the type filter ANDed in."""
    scoped = {_rewrite_key(key, pathway_model): value for key, value in (alternative or {}).items()}
    types = list(pathway_types)
    existing = scoped.pop("pathway_type__in", None)
    if existing is not None:
        if not isinstance(existing, list):
            raise UntranslatableConstraint(f"'pathway_type__in' is not a list: {existing!r}")
        types = [t for t in types if t in existing]
    scoped["pathway_type__in"] = types
    return scoped


def rewrite_constraints(constraints, pathway_types, *, pathway_model=None):
    """Translate a subtype permission's constraints onto the flattened pathway.

    Legacy field names are renamed (`conduit_bank` -> `parent` and so on, see
    CONSTRAINT_RENAMES) and `pathway_type__in=pathway_types` is ANDed into
    the single dict or into every alternative of a list, so the permission
    keeps matching only the types it used to. No constraint at all becomes
    the type filter alone. A key that does not resolve raises
    UntranslatableConstraint rather than being dropped, since dropping a
    condition would widen access.

    `pathway_model` defaults to the live model; migrations pass the
    historical one.
    """
    if pathway_model is None:
        from django.apps import apps

        pathway_model = apps.get_model("netbox_pathways", "Pathway")
    if isinstance(constraints, list) and constraints:
        return [_scope_to_types(alt, pathway_types, pathway_model) for alt in constraints]
    if isinstance(constraints, list):
        constraints = None
    return _scope_to_types(constraints, pathway_types, pathway_model)


def _m2m_columns(field):
    """(owner attname, target attname) on the through table of an M2M field."""
    through = field.remote_field.through._meta
    return (
        through.get_field(field.m2m_field_name()).attname,
        through.get_field(field.m2m_reverse_field_name()).attname,
    )


def _legacy_types_by_ct(apps, legacy_ct_ids):
    """{legacy content type id: pathway_type}, in LEGACY_SUBTYPES order."""
    ContentType = apps.get_model("contenttypes", "ContentType")
    names = dict(ContentType.objects.filter(pk__in=legacy_ct_ids).values_list("pk", "model"))
    order = list(LEGACY_SUBTYPES)
    return {pk: LEGACY_SUBTYPES[name] for pk, name in sorted(names.items(), key=lambda item: order.index(item[1]))}


def convert_object_permissions(apps, legacy_ct_ids, pathway_ct_id):
    """Give every permission on a subtype content type an equivalent on `pathway`.

    The original permission's constraints may also govern its other object
    types, so the pathway content type is not added to it. Instead a new
    permission named "<name> (pathways)" carries the same actions, users,
    groups and enabled flag, the pathway content type only, and the
    original constraints rewritten and scoped to the pathway types it
    covered. The subtype content types are then removed from the original,
    which is deleted if nothing remains on it.

    Every constraint is translated before anything is written; any that
    cannot be raise one UntranslatableConstraint naming each permission.
    """
    ObjectPermission = apps.get_model("users", "ObjectPermission")
    Pathway = apps.get_model("netbox_pathways", "Pathway")
    field = ObjectPermission._meta.get_field("object_types")
    through = field.remote_field.through
    owner_col, type_col = _m2m_columns(field)
    legacy_types = _legacy_types_by_ct(apps, legacy_ct_ids)

    planned, errors = [], []
    for perm in ObjectPermission.objects.filter(object_types__in=legacy_ct_ids).distinct().order_by("pk"):
        covered = set(
            through.objects.filter(**{owner_col: perm.pk, f"{type_col}__in": legacy_ct_ids}).values_list(
                type_col, flat=True
            )
        )
        types = [pathway_type for pk, pathway_type in legacy_types.items() if pk in covered]
        try:
            planned.append((perm, rewrite_constraints(perm.constraints, types, pathway_model=Pathway)))
        except UntranslatableConstraint as exc:
            errors.append(f"{perm.name!r} (id {perm.pk}): {exc}")
    if errors:
        raise UntranslatableConstraint(
            "These object permissions cannot be moved onto the pathway model; "
            "fix or remove their constraints and run the migration again:\n  " + "\n  ".join(errors)
        )

    name_length = ObjectPermission._meta.get_field("name").max_length - len(PERMISSION_SUFFIX)
    for perm, constraints in planned:
        converted = ObjectPermission.objects.create(
            name=f"{perm.name[:name_length]}{PERMISSION_SUFFIX}",
            description=perm.description,
            enabled=perm.enabled,
            actions=list(perm.actions),
            constraints=constraints,
        )
        converted.object_types.add(pathway_ct_id)
        converted.users.set(perm.users.all())
        converted.groups.set(perm.groups.all())
        through.objects.filter(**{owner_col: perm.pk, f"{type_col}__in": legacy_ct_ids}).delete()
        if not through.objects.filter(**{owner_col: perm.pk}).exists():
            perm.delete()


def _repoint_fk(model, field, legacy_ct_ids, pathway_ct_id):
    """Point one content-type foreign key at `pathway`; return the duplicates dropped.

    A row whose repointed values collide with a unique constraint is a
    second reference to the same pathway (it was reachable through both the
    pathway and its subtype content type), so it is deleted.
    """
    manager = model._base_manager
    rows = manager.filter(**{f"{field.attname}__in": legacy_ct_ids})
    try:
        with transaction.atomic():
            rows.update(**{field.attname: pathway_ct_id})
        return 0
    except IntegrityError:
        pass
    dropped = 0
    for pk in list(rows.values_list("pk", flat=True)):
        try:
            with transaction.atomic():
                manager.filter(pk=pk).update(**{field.attname: pathway_ct_id})
        except IntegrityError:
            manager.filter(pk=pk).delete()
            dropped += 1
    return dropped


def _repoint_m2m(field, legacy_ct_ids, pathway_ct_id):
    """Replace the subtype content types with `pathway` on one M2M, once per owner."""
    through = field.remote_field.through
    owner_col, type_col = _m2m_columns(field)
    legacy_rows = through.objects.filter(**{f"{type_col}__in": legacy_ct_ids})
    owners = set(legacy_rows.values_list(owner_col, flat=True))
    if owners:
        through.objects.bulk_create(
            [through(**{owner_col: owner, type_col: pathway_ct_id}) for owner in owners], ignore_conflicts=True
        )
        legacy_rows.delete()


def repoint_content_type_references(apps, legacy_ct_ids, pathway_ct_id):
    """Move every reference to a subtype content type onto `pathway`.

    Introspects every model in `apps`, so history, tags, journal entries,
    image attachments, bookmarks, subscriptions, custom field and export
    template assignments and any other app's content-type columns all move,
    with no list to keep current. Primary keys did not change in the
    flatten, so the object ids that go with each content type stay valid.
    """
    for model in apps.get_models():
        opts = model._meta
        if opts.proxy or not opts.managed:
            continue
        for field in opts.local_fields:
            if (
                field.many_to_one
                and field.related_model._meta.label_lower in CONTENT_TYPE_MODELS
                and (opts.label_lower, field.name) not in REPOINT_SKIPPED
            ):
                dropped = _repoint_fk(model, field, legacy_ct_ids, pathway_ct_id)
                if dropped:
                    print(
                        f"\n  netbox_pathways: dropped {dropped} {opts.label} row(s) that duplicated "
                        f"a reference to the same pathway."
                    )
        for field in opts.local_many_to_many:
            if (
                field.related_model._meta.label_lower in CONTENT_TYPE_MODELS
                and field.remote_field.through._meta.auto_created
                and (opts.label_lower, field.name) not in REPOINT_SKIPPED
            ):
                _repoint_m2m(field, legacy_ct_ids, pathway_ct_id)


def _duplicated_custom_field_values(pathway_model, names):
    """The subset of `names` whose non-empty values repeat across pathways."""
    seen = {name: set() for name in names}
    duplicated = set()
    for data in pathway_model.objects.values_list("custom_field_data", flat=True).iterator(chunk_size=BATCH_SIZE):
        for name in names:
            value = (data or {}).get(name)
            if value in (None, ""):
                continue
            key = json.dumps(value, sort_keys=True)
            if key in seen[name]:
                duplicated.add(name)
            seen[name].add(key)
    return duplicated


def relax_custom_fields(apps, legacy_ct_ids, pathway_ct_id):
    """Clear the flags a custom field cannot keep once it applies to every pathway.

    Run before the content-type references move, while each field's subtype
    assignments are still visible. A `unique` field whose values repeat
    across the merged rows loses `unique`. A `required` field loses
    `required` unless it already applied to the pathway model or to all of
    the former subtypes, since it would otherwise become mandatory for
    types it never covered. Returns one log line per flag cleared.
    """
    CustomField = apps.get_model("extras", "CustomField")
    Pathway = apps.get_model("netbox_pathways", "Pathway")
    field = CustomField._meta.get_field("object_types")
    through = field.remote_field.through
    owner_col, type_col = _m2m_columns(field)
    legacy = set(legacy_ct_ids)

    fields = list(CustomField.objects.filter(object_types__in=legacy).distinct().order_by("name"))
    duplicated = _duplicated_custom_field_values(Pathway, [cf.name for cf in fields if cf.unique])
    log = []
    for cf in fields:
        covered = set(through.objects.filter(**{owner_col: cf.pk}).values_list(type_col, flat=True))
        cleared = []
        if cf.unique and cf.name in duplicated:
            cf.unique = False
            cleared.append("unique")
            log.append(f"custom field '{cf.name}': cleared 'unique', its values repeat across pathway types.")
        if cf.required and pathway_ct_id not in covered and not legacy <= covered:
            cf.required = False
            cleared.append("required")
            log.append(f"custom field '{cf.name}': cleared 'required', it applied to only some pathway types.")
        if cleared:
            cf.save(update_fields=cleared)
    return log


def retire_subtype_content_types(apps, schema_editor):
    """Move everything keyed on the five subtype content types to `pathway`, then delete them.

    Permissions go first: an untranslatable constraint aborts the migration
    before any row has moved. Custom field flags are relaxed next, while the
    subtype assignments still show which types each field covered. A
    database that never had the subtypes (a fresh install) has nothing to do.
    """
    ContentType = apps.get_model("contenttypes", "ContentType")
    legacy = ContentType.objects.filter(app_label="netbox_pathways", model__in=list(LEGACY_SUBTYPES))
    legacy_ct_ids = list(legacy.values_list("pk", flat=True))
    if not legacy_ct_ids:
        return
    pathway_ct, _ = ContentType.objects.get_or_create(app_label="netbox_pathways", model="pathway")

    convert_object_permissions(apps, legacy_ct_ids, pathway_ct.pk)
    for line in relax_custom_fields(apps, legacy_ct_ids, pathway_ct.pk):
        print(f"\n  netbox_pathways: {line}")
    repoint_content_type_references(apps, legacy_ct_ids, pathway_ct.pk)
    ContentType.objects.filter(pk__in=legacy_ct_ids).delete()

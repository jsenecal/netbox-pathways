"""Import geodata from shapefiles, GeoJSON, etc. using a YAML schema file.

Usage:
    python manage.py import_geodata /path/to/data.shp --schema schema.yaml
    python manage.py import_geodata /path/to/data.shp --schema schema.yaml --dry-run
    python manage.py import_geodata /path/to/data.shp --schema schema.yaml --limit 10
    python manage.py import_geodata /path/to/data.shp --schema schema.yaml --update
    python manage.py import_geodata /path/to/data.shp --schema schema.yaml --workers 8
"""

import datetime
import multiprocessing
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed

import yaml
from django.contrib.gis.gdal import DataSource
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db import models as db_models

from netbox_pathways.geo import get_srid
from netbox_pathways.models import (
    AerialSpan,
    CircuitGeometry,
    Conduit,
    ConduitBank,
    DirectBuried,
    Innerduct,
    Structure,
)

MODEL_MAP = {
    "structure": Structure,
    "conduit": Conduit,
    "aerial_span": AerialSpan,
    "direct_buried": DirectBuried,
    "innerduct": Innerduct,
    "conduit_bank": ConduitBank,
    "circuit_geometry": CircuitGeometry,
}

TRANSFORMS = {
    "year_to_date": lambda v: datetime.date(int(v), 1, 1) if v and int(v) > 0 else None,
    "to_int": lambda v: int(v) if v is not None else None,
    "to_float": lambda v: float(v) if v is not None else None,
    "to_bool": lambda v: bool(int(v)) if v is not None else False,
    "to_str": lambda v: str(v) if v is not None else "",
    "boolean_flag": lambda v: bool(int(v)) if v is not None else False,
}


def _deserialize_kwargs(row, geom_field):
    """Reconstruct kwargs from serialized row (EWKT geometry, FK tuples)."""
    from django.apps import apps
    from django.contrib.gis.geos import GEOSGeometry

    kwargs = {}
    for key, value in row.items():
        if key == geom_field:
            kwargs[key] = GEOSGeometry(value)
        elif isinstance(value, tuple) and len(value) == 3 and value[0] == "__fk__":
            fk_model = apps.get_model(value[1])
            kwargs[key] = fk_model(pk=value[2])
        else:
            kwargs[key] = value
    return kwargs


def _save_batch(model_name, batch_rows, geom_field, children_specs=None):
    """Save a batch of model instances in a forked worker process.

    If children_specs is provided, also creates child records for each
    saved parent. Children inherit geometry, endpoints, and tenant from
    the parent.
    """
    from django.db import connection

    connection.close()
    connection.ensure_connection()

    model_class = MODEL_MAP[model_name]
    saved = 0
    errors = []
    for row in batch_rows:
        try:
            kwargs = _deserialize_kwargs(row, geom_field)
            obj = model_class(**kwargs)
            obj.save()
            saved += 1

            # Create child records
            if children_specs:
                for child_spec in children_specs:
                    child_model = MODEL_MAP[child_spec["model"]]
                    child_geom_field = child_spec.get("geometry_field", geom_field)
                    child_name_tmpl = child_spec.get("name_template", "")
                    parent_fk_field = child_spec.get("parent_fk_field")

                    child_kwargs = {}
                    # Inherit common fields from parent
                    for field in (
                        "tenant",
                        "start_structure",
                        "end_structure",
                        "start_location",
                        "end_location",
                        "length",
                    ):
                        if field in kwargs:
                            child_kwargs[field] = kwargs[field]
                    # Inherit geometry
                    if geom_field in kwargs:
                        child_kwargs[child_geom_field] = kwargs[geom_field]
                    # Set parent FK
                    if parent_fk_field:
                        child_kwargs[parent_fk_field] = obj
                    # Set label (or name for Structure children)
                    if child_name_tmpl:
                        name_field = "label" if hasattr(child_model, "label") else "name"
                        parent_name_field = "label" if "label" in kwargs else "name"
                        child_kwargs[name_field] = child_name_tmpl.replace(
                            "{_parent_name}",
                            kwargs.get(parent_name_field, ""),
                        )

                    child_obj = child_model(**child_kwargs)
                    child_obj.save()
                    saved += 1

        except Exception as e:
            errors.append(str(e))

    connection.close()
    return saved, errors


class Command(BaseCommand):
    help = "Import geodata from shapefiles, GeoJSON, etc. using a YAML schema file."

    def add_arguments(self, parser):
        parser.add_argument("source", help="Path to geodata file (shapefile, GeoJSON, etc.)")
        parser.add_argument("--schema", required=True, help="Path to YAML schema file")
        parser.add_argument("--dry-run", action="store_true", help="Preview import without saving")
        parser.add_argument("--batch-size", type=int, default=500, help="Batch size for bulk_create")
        parser.add_argument("--update", action="store_true", help="Update existing records by name")
        parser.add_argument("--limit", type=int, help="Max records to import")
        parser.add_argument(
            "--workers",
            type=int,
            default=4,
            help="Number of worker threads for non-bulk saves (default: 4)",
        )

    def _log(self, msg, style=None, flush=True):
        """Write a message to stdout and flush immediately."""
        if style:
            msg = style(msg)
        self.stdout.write(msg)
        if flush:
            sys.stdout.flush()

    def handle(self, *args, **options):
        t0 = time.time()
        schema = self._load_schema(options["schema"])

        try:
            ds = DataSource(options["source"])
        except Exception as e:
            raise CommandError(f"Cannot open geodata source: {e}") from e

        layer_index = schema.get("layer", 0)
        layer = ds[layer_index]
        self._log(f"Source: {options['source']}")
        self._log(f"  Layer: {layer.name} ({layer.num_feat} features, {layer.geom_type})")
        self._log(f"  Fields: {', '.join(layer.fields)}")

        # Resolve model
        model_name = schema.get("model", "")
        model_class = MODEL_MAP.get(model_name)
        if not model_class:
            raise CommandError(f"Unknown model '{model_name}'. Options: {', '.join(MODEL_MAP)}")

        # Resolve SRIDs — reproject via ogr2ogr if needed
        source_srid = self._resolve_srid(schema, layer)
        storage_srid = get_srid()
        self._log(f"  Source SRID: {source_srid} -> Storage SRID: {storage_srid}")

        temp_dir = None
        if source_srid != storage_srid:
            self._log("  Reprojecting via ogr2ogr...")
            temp_dir = tempfile.mkdtemp(prefix="geodata_import_")
            src_path = options["source"]
            base = os.path.splitext(os.path.basename(src_path))[0]
            reprojected = os.path.join(temp_dir, base + ".shp")
            result = subprocess.run(
                ["ogr2ogr", reprojected, src_path, "-t_srs", f"EPSG:{storage_srid}", "-overwrite"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise CommandError(f"ogr2ogr failed: {result.stderr}")
            ds = DataSource(reprojected)
            layer = ds[layer_index]
            source_srid = storage_srid
            self._log(f"  Reprojected to {reprojected}")

        geom_field = schema.get("geometry_field", "location")
        field_specs = schema.get("fields", {})
        filters = schema.get("filters", {})
        excludes = schema.get("exclude", {})

        # Normalize field specs: string shorthand -> dict
        for src, spec in list(field_specs.items()):
            if isinstance(spec, str):
                field_specs[src] = {"to": spec}

        # Resolve FK defaults
        defaults = self._resolve_defaults(schema.get("defaults", {}), model_class)

        # Separate field specs into categories
        fk_specs = {}
        aggregate_specs = {}
        direct_specs = {}
        for src, spec in field_specs.items():
            if isinstance(spec, dict) and spec.get("fk_template"):
                fk_specs[src] = spec
            elif isinstance(spec, dict) and spec.get("label"):
                target = spec.get("to", "comments")
                aggregate_specs.setdefault(target, {})[src] = spec
            else:
                direct_specs[src] = spec

        # Pre-load FK caches
        self._log("  Loading FK caches...")
        fk_caches = {}
        for src, spec in fk_specs.items():
            target = spec["to"]
            related_model = self._get_related_model(model_class, target)
            if related_model is None:
                raise CommandError(f"Field '{target}' on {model_class.__name__} is not a ForeignKey")
            cache_regex = spec.get("fk_cache_regex")
            cache_pattern = re.compile(cache_regex) if cache_regex else None
            cache = {}
            for obj in related_model.objects.only("pk", "name"):
                if cache_pattern:
                    m = cache_pattern.search(obj.name)
                    if m:
                        cache[m.group(1)] = obj
                else:
                    cache[obj.name] = obj
            fk_caches[src] = cache
            self._log(f"  FK cache for {target}: {len(cache)} {related_model.__name__} objects")

        # Parse children specs from schema
        children_specs = []
        for child_def in schema.get("children", []):
            child_model_name = child_def["model"]
            if child_model_name not in MODEL_MAP:
                raise CommandError(f"Unknown child model '{child_model_name}'")
            # Find which field on the child model points to the parent
            parent_fk_field = None
            child_model_class = MODEL_MAP[child_model_name]
            for field in child_model_class._meta.get_fields():
                if isinstance(field, db_models.ForeignKey) and field.related_model is model_class:
                    parent_fk_field = field.name
                    break
            if child_def.get("fields"):
                for spec in child_def["fields"].values():
                    if spec.get("from_parent"):
                        parent_fk_field = spec["to"]
                        break
            children_specs.append(
                {
                    "model": child_model_name,
                    "geometry_field": child_def.get("geometry_field", geom_field),
                    "name_template": child_def.get("name_template", ""),
                    "parent_fk_field": parent_fk_field,
                }
            )
        if children_specs:
            self._log(f"  Children: {', '.join(c['model'] for c in children_specs)}")

        # Detect if bulk_create is available
        use_bulk = not model_class._meta.parents and not children_specs

        # ── Phase 1: Read and transform all features ──
        limit = options.get("limit") or layer.num_feat
        dry_run = options["dry_run"]
        name_counts = Counter()
        all_kwargs = []
        skipped = 0
        fk_misses = Counter()
        read_errors = []

        self._log(f"\n[Phase 1] Reading {min(limit, layer.num_feat)} features...")
        t1 = time.time()

        for i, feature in enumerate(layer):
            if i >= limit:
                break

            if (i + 1) % 5000 == 0:
                elapsed = time.time() - t1
                rate = (i + 1) / elapsed
                self._log(f"  {i + 1:,} read ({rate:,.0f}/s, {skipped:,} skipped)...")

            if not self._passes_filters(feature, filters):
                skipped += 1
                continue

            if excludes and self._passes_filters(feature, excludes):
                skipped += 1
                continue

            try:
                kwargs = dict(defaults)

                # Raw source values
                raw = {}
                for fname in layer.fields:
                    raw[fname] = feature.get(fname)

                # Name/label template with duplicate suffixing
                name_template = schema.get("name_template")
                if name_template:
                    name_field = "label" if hasattr(model_class, "label") else "name"
                    base_name = name_template.format(**raw)
                    name_counts[base_name] += 1
                    count = name_counts[base_name]
                    kwargs[name_field] = base_name if count == 1 else f"{base_name}-{count}"

                # Geometry — force 2D
                ogr_geom = feature.geom
                ogr_geom.coord_dim = 2
                geom = ogr_geom.geos
                geom.srid = source_srid
                if source_srid != storage_srid:
                    geom.transform(storage_srid)
                kwargs[geom_field] = geom

                # FK template lookups
                fk_ok = True
                for src_field, spec in fk_specs.items():
                    value = raw.get(src_field)
                    template = spec["fk_template"]
                    lookup_name = template.format(value=value)
                    obj = fk_caches[src_field].get(lookup_name)
                    if obj is None:
                        fk_misses[lookup_name] += 1
                        fk_ok = False
                        break
                    kwargs[spec["to"]] = obj
                if not fk_ok:
                    skipped += 1
                    continue

                # Direct field mappings
                for src_field, spec in direct_specs.items():
                    actual_src = spec.get("source", src_field)
                    value = raw.get(actual_src)
                    target = spec.get("to")
                    if not target:
                        continue
                    mapped = self._apply_field_spec(value, spec)
                    if mapped is not None:
                        kwargs[target] = mapped

                # Aggregate labeled fields
                for target_field, specs in aggregate_specs.items():
                    parts = []
                    for src_field, spec in specs.items():
                        value = raw.get(src_field)
                        if value is None or not str(value).strip():
                            continue
                        transform_name = spec.get("transform")
                        if transform_name:
                            transform_fn = TRANSFORMS.get(transform_name)
                            if transform_fn:
                                value = transform_fn(value)
                        if spec.get("transform") == "boolean_flag":
                            if value:
                                parts.append(spec["label"])
                        elif str(value).strip():
                            parts.append(f"{spec['label']}: {value}")
                    if parts:
                        existing = kwargs.get(target_field, "")
                        joined = "\n".join(parts)
                        kwargs[target_field] = f"{existing}\n{joined}".strip() if existing else joined

                all_kwargs.append(kwargs)

            except Exception as e:
                read_errors.append((i + 1, str(e)))
                if len(read_errors) <= 3:
                    self._log(f"  Row {i + 1}: {e}", style=self.style.ERROR)

        read_time = time.time() - t1
        self._log(
            f"  Done: {len(all_kwargs):,} records prepared, "
            f"{skipped:,} skipped, {len(read_errors)} errors "
            f"({read_time:.1f}s)"
        )

        # ── Dry run: show samples and exit ──
        if dry_run:
            self._log("")
            self._log("DRY RUN - no records saved", style=self.style.WARNING)
            self._log(f"Would create: {len(all_kwargs)}")
            self._log(f"Filtered out: {skipped}")
            for j, kwargs in enumerate(all_kwargs[:5]):
                display = {}
                for k, v in kwargs.items():
                    s = str(v)
                    display[k] = s[:60] + "..." if len(s) > 60 else v
                self._log(f"  [{j + 1}] {display}")
            self._report_misses(fk_misses)
            self._report_errors(read_errors)
            return

        # ── Phase 2: Save records ──
        created_count = 0
        updated_count = 0
        save_errors = []
        t2 = time.time()
        total = len(all_kwargs)

        if options["update"]:
            self._log(f"\n[Phase 2] Updating/creating {total:,} records...")
            name_field = "label" if hasattr(model_class, "label") else "name"
            for j, kwargs in enumerate(all_kwargs):
                try:
                    lookup_val = kwargs.get(name_field, f"import-{j}")
                    update_kwargs = {k: v for k, v in kwargs.items() if k != name_field}
                    _, was_created = model_class.objects.update_or_create(
                        **{name_field: lookup_val},
                        defaults=update_kwargs,
                    )
                    if was_created:
                        created_count += 1
                    else:
                        updated_count += 1
                except Exception as e:
                    save_errors.append((j + 1, str(e)))
                if (j + 1) % 1000 == 0:
                    elapsed = time.time() - t2
                    rate = (j + 1) / elapsed
                    self._log(
                        f"  {j + 1:,}/{total:,} ({created_count:,} new, {updated_count:,} updated, {rate:,.0f}/s)..."
                    )

        elif use_bulk:
            self._log(f"\n[Phase 2] Bulk creating {total:,} records (batch={options['batch_size']})...")
            batch_size = options["batch_size"]
            for start in range(0, total, batch_size):
                chunk = [model_class(**kw) for kw in all_kwargs[start : start + batch_size]]
                try:
                    model_class.objects.bulk_create(chunk)
                    created_count += len(chunk)
                except Exception as e:
                    save_errors.append((start + 1, str(e)))
                if created_count % 5000 < batch_size:
                    elapsed = time.time() - t2
                    rate = created_count / elapsed if elapsed > 0 else 0
                    self._log(f"  {created_count:,}/{total:,} ({rate:,.0f}/s)...")

        else:
            # Multi-table inheritance — use multiprocessing for true parallelism
            workers = min(options["workers"], os.cpu_count() or 4)
            self._log(f"\n[Phase 2] Saving {total:,} records ({workers} worker processes)...")

            # Serialize kwargs for pickling across process boundaries:
            # - Geometry → EWKT string
            # - FK objects → ('__fk__', 'app_label.ModelName', pk) tuple
            self._log("  Serializing for multiprocessing...")
            serialized = []
            for kwargs in all_kwargs:
                row = {}
                for key, value in kwargs.items():
                    if hasattr(value, "ewkt"):
                        row[key] = value.ewkt
                    elif hasattr(value, "_meta") and hasattr(value, "pk"):
                        label = f"{value._meta.app_label}.{value._meta.model_name}"
                        row[key] = ("__fk__", label, value.pk)
                    else:
                        row[key] = value
                serialized.append(row)

            chunk_size = max(100, total // (workers * 4))
            chunks = [serialized[i : i + chunk_size] for i in range(0, total, chunk_size)]
            self._log(f"  {len(chunks)} chunks of ~{chunk_size}")

            # Close DB connections before forking
            connections.close_all()

            with ProcessPoolExecutor(
                max_workers=workers,
                mp_context=multiprocessing.get_context("fork"),
            ) as executor:
                futures = {
                    executor.submit(
                        _save_batch,
                        model_name,
                        chunk,
                        geom_field,
                        children_specs or None,
                    ): len(chunk)
                    for chunk in chunks
                }
                for future in as_completed(futures):
                    saved, errs = future.result()
                    created_count += saved
                    for err in errs:
                        save_errors.append((0, err))
                    elapsed = time.time() - t2
                    rate = created_count / elapsed if elapsed > 0 else 0
                    self._log(f"  {created_count:,}/{total:,} ({rate:,.0f}/s, {len(save_errors)} errors)...")

        save_time = time.time() - t2
        total_time = time.time() - t0

        # ── Report ──
        self._log("")
        self._log("Import complete!", style=self.style.SUCCESS)
        self._log(f"  Created: {created_count:,}")
        if updated_count:
            self._log(f"  Updated: {updated_count:,}")
        self._log(f"  Filtered out: {skipped:,}")
        self._log(f"  Time: {read_time:.1f}s read + {save_time:.1f}s save = {total_time:.1f}s total")
        if created_count > 0 and save_time > 0:
            self._log(f"  Save rate: {created_count / save_time:,.0f} records/s")

        self._report_misses(fk_misses)
        all_errors = read_errors + save_errors
        self._report_errors(all_errors)

        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _report_misses(self, fk_misses):
        if not fk_misses:
            return
        total_misses = sum(fk_misses.values())
        self._log(
            f"  FK lookup misses: {total_misses} features skipped ({len(fk_misses)} distinct names)",
            style=self.style.WARNING,
        )
        for name, count in fk_misses.most_common(10):
            self._log(f'    "{name}": {count} references')
        if len(fk_misses) > 10:
            self._log(f"    ... and {len(fk_misses) - 10} more")

    def _report_errors(self, errors):
        if not errors:
            return
        self._log(f"  Errors: {len(errors)}", style=self.style.ERROR)
        for row, msg in errors[:10]:
            self._log(f"    Row {row}: {msg}")
        if len(errors) > 10:
            self._log(f"    ... and {len(errors) - 10} more")

    def _load_schema(self, path):
        try:
            with open(path) as f:
                return yaml.safe_load(f)
        except FileNotFoundError as e:
            raise CommandError(f"Schema file not found: {path}") from e
        except yaml.YAMLError as e:
            raise CommandError(f"Invalid YAML in schema file: {e}") from e

    def _resolve_srid(self, schema, layer):
        source_srid = schema.get("source_srid", "auto")
        if source_srid != "auto":
            return int(source_srid)

        srs = layer.srs
        if srs:
            try:
                if hasattr(srs, "identify_epsg"):
                    srs.identify_epsg()
                if srs.srid:
                    return srs.srid
            except Exception:  # noqa: S110
                pass

        raise CommandError(
            "Cannot auto-detect source SRID from file. Set 'source_srid' in the schema file (e.g., source_srid: 32188)."
        )

    def _resolve_defaults(self, defaults_spec, model_class):
        """Resolve default values, looking up FK references by slug or name."""
        resolved = {}
        for field_name, value in defaults_spec.items():
            try:
                field = model_class._meta.get_field(field_name)
            except Exception:
                resolved[field_name] = value
                continue

            if isinstance(field, db_models.ForeignKey):
                related_model = field.related_model
                obj = self._resolve_fk(related_model, value)
                resolved[field_name] = obj
            else:
                resolved[field_name] = value

        return resolved

    def _resolve_fk(self, model, value):
        """Look up a FK reference by PK, slug, or name."""
        if isinstance(value, int):
            try:
                return model.objects.get(pk=value)
            except model.DoesNotExist as e:
                raise CommandError(f"{model.__name__} with pk={value} not found") from e

        # Try slug
        try:
            model._meta.get_field("slug")
            try:
                return model.objects.get(slug=value)
            except model.DoesNotExist:
                pass
        except Exception:  # noqa: S110
            pass

        # Try name
        try:
            model._meta.get_field("name")
            try:
                return model.objects.get(name=value)
            except model.DoesNotExist:
                pass
        except Exception:  # noqa: S110
            pass

        raise CommandError(f"{model.__name__} not found with slug or name '{value}'. Create it in NetBox first.")

    def _get_related_model(self, model_class, field_name):
        """Return the related model for a FK field, or None if not a FK."""
        try:
            field = model_class._meta.get_field(field_name)
        except Exception:
            return None
        if isinstance(field, db_models.ForeignKey):
            return field.related_model
        return None

    def _passes_filters(self, feature, filters):
        for field, expected in filters.items():
            value = feature.get(field)
            if str(value).strip() != str(expected).strip():
                return False
        return True

    def _apply_field_spec(self, value, spec):
        """Apply a field specification to transform a source value.

        Processing order: regex → map → transform → format.
        Each step feeds into the next if both are present.
        """
        if not isinstance(spec, dict):
            return value

        # Regex extraction
        if "regex" in spec:
            str_value = str(value) if value is not None else ""
            m = re.search(spec["regex"], str_value)
            if m:
                group = spec.get("regex_group", 1)
                value = m.group(group)
            else:
                return spec.get("default")

        # Value mapping
        if "map" in spec:
            str_value = str(value).strip() if value is not None else ""
            mapped = spec["map"].get(str_value)
            if mapped is not None:
                return mapped
            return spec.get("default")

        # Transform function
        if "transform" in spec:
            transform_name = spec["transform"]
            transform_fn = TRANSFORMS.get(transform_name)
            if not transform_fn:
                raise CommandError(f"Unknown transform: {transform_name}")
            return transform_fn(value)

        # Format template
        if "format" in spec:
            try:
                return spec["format"].format(value=value)
            except (ValueError, KeyError):
                return str(value)

        return value

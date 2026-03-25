"""Import geodata from shapefiles, GeoJSON, etc. using a YAML schema file.

Usage:
    python manage.py import_geodata /path/to/data.shp --schema schema.yaml
    python manage.py import_geodata /path/to/data.shp --schema schema.yaml --dry-run
    python manage.py import_geodata /path/to/data.shp --schema schema.yaml --limit 10
    python manage.py import_geodata /path/to/data.shp --schema schema.yaml --update
"""

import datetime

import yaml
from django.contrib.gis.gdal import DataSource
from django.core.management.base import BaseCommand, CommandError
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
    'structure': Structure,
    'conduit': Conduit,
    'aerial_span': AerialSpan,
    'direct_buried': DirectBuried,
    'innerduct': Innerduct,
    'conduit_bank': ConduitBank,
    'circuit_geometry': CircuitGeometry,
}

TRANSFORMS = {
    'year_to_date': lambda v: datetime.date(int(v), 1, 1) if v and int(v) > 0 else None,
    'to_int': lambda v: int(v) if v is not None else None,
    'to_float': lambda v: float(v) if v is not None else None,
    'to_bool': lambda v: bool(int(v)) if v is not None else False,
    'to_str': lambda v: str(v) if v is not None else '',
    'boolean_flag': lambda v: bool(int(v)) if v is not None else False,
}


class Command(BaseCommand):
    help = 'Import geodata from shapefiles, GeoJSON, etc. using a YAML schema file.'

    def add_arguments(self, parser):
        parser.add_argument('source', help='Path to geodata file (shapefile, GeoJSON, etc.)')
        parser.add_argument('--schema', required=True, help='Path to YAML schema file')
        parser.add_argument('--dry-run', action='store_true', help='Preview import without saving')
        parser.add_argument('--batch-size', type=int, default=500, help='Batch size for bulk_create')
        parser.add_argument('--update', action='store_true', help='Update existing records by name')
        parser.add_argument('--limit', type=int, help='Max records to import')

    def handle(self, *args, **options):
        schema = self._load_schema(options['schema'])

        try:
            ds = DataSource(options['source'])
        except Exception as e:
            raise CommandError(f"Cannot open geodata source: {e}")

        layer_index = schema.get('layer', 0)
        layer = ds[layer_index]
        self.stdout.write(f'Source: {options["source"]}')
        self.stdout.write(f'  Layer: {layer.name} ({layer.num_feat} features, {layer.geom_type})')
        self.stdout.write(f'  Fields: {", ".join(layer.fields)}')

        # Resolve model
        model_name = schema.get('model', '')
        model_class = MODEL_MAP.get(model_name)
        if not model_class:
            raise CommandError(f"Unknown model '{model_name}'. Options: {', '.join(MODEL_MAP)}")

        # Resolve SRIDs
        source_srid = self._resolve_srid(schema, layer)
        storage_srid = get_srid()
        self.stdout.write(f'  Source SRID: {source_srid} -> Storage SRID: {storage_srid}')

        geom_field = schema.get('geometry_field', 'location')
        field_specs = schema.get('fields', {})
        filters = schema.get('filters', {})

        # Normalize field specs: string shorthand -> dict
        for src, spec in list(field_specs.items()):
            if isinstance(spec, str):
                field_specs[src] = {'to': spec}

        # Resolve FK defaults
        defaults = self._resolve_defaults(schema.get('defaults', {}), model_class)

        # Separate labeled-aggregate fields (multiple source fields → one text field)
        # from direct 1:1 field mappings. Grouped by target field name.
        aggregate_specs = {}  # {target_field: {src_field: spec, ...}}
        direct_specs = {}
        for src, spec in field_specs.items():
            if isinstance(spec, dict) and spec.get('label'):
                target = spec.get('to', 'comments')
                aggregate_specs.setdefault(target, {})[src] = spec
            else:
                direct_specs[src] = spec

        # Process features
        batch = []
        created_count = 0
        updated_count = 0
        skipped = 0
        errors = []
        limit = options.get('limit') or layer.num_feat
        dry_run = options['dry_run']

        self.stdout.write(f'\nImporting up to {limit} features into {model_name}...')

        for i, feature in enumerate(layer):
            if i >= limit:
                break

            if not self._passes_filters(feature, filters):
                skipped += 1
                continue

            try:
                kwargs = dict(defaults)

                # Build a dict of all raw source values for templates
                raw = {}
                for fname in layer.fields:
                    raw[fname] = feature.get(fname)

                # Apply name_template if present (can reference any source field)
                name_template = schema.get('name_template')
                if name_template:
                    kwargs['name'] = name_template.format(**raw)

                # Map geometry
                geom = feature.geom.geos
                geom.srid = source_srid
                if source_srid != storage_srid:
                    geom.transform(storage_srid)
                kwargs[geom_field] = geom

                # Map direct fields
                for src_field, spec in direct_specs.items():
                    value = raw.get(src_field)
                    target = spec.get('to')
                    if not target:
                        continue
                    mapped = self._apply_field_spec(value, spec)
                    if mapped is not None:
                        kwargs[target] = mapped

                # Aggregate labeled fields into their target text fields
                for target_field, specs in aggregate_specs.items():
                    parts = []
                    for src_field, spec in specs.items():
                        value = raw.get(src_field)
                        if value is None or not str(value).strip():
                            continue
                        # Apply transform if present (e.g. boolean_flag)
                        transform_name = spec.get('transform')
                        if transform_name:
                            transform_fn = TRANSFORMS.get(transform_name)
                            if transform_fn:
                                value = transform_fn(value)
                        # For boolean flags, only include if truthy
                        if spec.get('transform') == 'boolean_flag':
                            if value:
                                parts.append(spec['label'])
                        elif str(value).strip():
                            parts.append(f"{spec['label']}: {value}")
                    if parts:
                        existing = kwargs.get(target_field, '')
                        joined = '\n'.join(parts)
                        kwargs[target_field] = f"{existing}\n{joined}".strip() if existing else joined

                if dry_run:
                    if len(batch) < 5:
                        batch.append(kwargs)
                    created_count += 1
                elif options['update']:
                    name = kwargs.get('name', f'import-{i}')
                    update_kwargs = {k: v for k, v in kwargs.items() if k != 'name'}
                    _, was_created = model_class.objects.update_or_create(
                        name=name, defaults=update_kwargs,
                    )
                    if was_created:
                        created_count += 1
                    else:
                        updated_count += 1
                else:
                    batch.append(model_class(**kwargs))
                    if len(batch) >= options['batch_size']:
                        model_class.objects.bulk_create(batch)
                        created_count += len(batch)
                        batch = []
                        self.stdout.write(f'  {created_count} created...')

            except Exception as e:
                errors.append((i + 1, str(e)))
                if len(errors) <= 3:
                    self.stdout.write(self.style.ERROR(f'  Row {i + 1}: {e}'))

        # Flush remaining batch
        if batch and not dry_run and not options['update']:
            model_class.objects.bulk_create(batch)
            created_count += len(batch)

        # Report
        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no records saved'))
            self.stdout.write(f'Would create: {created_count}')
            self.stdout.write(f'Filtered out: {skipped}')
            if batch:
                self.stdout.write('\nSample records:')
                for j, kwargs in enumerate(batch):
                    display = {}
                    for k, v in kwargs.items():
                        s = str(v)
                        display[k] = s[:60] + '...' if len(s) > 60 else v
                    self.stdout.write(f'  [{j + 1}] {display}')
        else:
            self.stdout.write(self.style.SUCCESS('Import complete!'))
            self.stdout.write(f'  Created: {created_count}')
            if updated_count:
                self.stdout.write(f'  Updated: {updated_count}')
            self.stdout.write(f'  Filtered out: {skipped}')

        if errors:
            self.stdout.write(self.style.ERROR(f'  Errors: {len(errors)}'))
            for row, msg in errors[:10]:
                self.stdout.write(f'    Row {row}: {msg}')
            if len(errors) > 10:
                self.stdout.write(f'    ... and {len(errors) - 10} more')

    def _load_schema(self, path):
        try:
            with open(path) as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise CommandError(f"Schema file not found: {path}")
        except yaml.YAMLError as e:
            raise CommandError(f"Invalid YAML in schema file: {e}")

    def _resolve_srid(self, schema, layer):
        source_srid = schema.get('source_srid', 'auto')
        if source_srid != 'auto':
            return int(source_srid)

        srs = layer.srs
        if srs:
            try:
                if hasattr(srs, 'identify_epsg'):
                    srs.identify_epsg()
                if srs.srid:
                    return srs.srid
            except Exception:
                pass

        raise CommandError(
            "Cannot auto-detect source SRID from file. "
            "Set 'source_srid' in the schema file (e.g., source_srid: 32188)."
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
            except model.DoesNotExist:
                raise CommandError(f"{model.__name__} with pk={value} not found")

        # Try slug
        try:
            model._meta.get_field('slug')
            try:
                return model.objects.get(slug=value)
            except model.DoesNotExist:
                pass
        except Exception:
            pass

        # Try name
        try:
            model._meta.get_field('name')
            try:
                return model.objects.get(name=value)
            except model.DoesNotExist:
                pass
        except Exception:
            pass

        raise CommandError(
            f"{model.__name__} not found with slug or name '{value}'. "
            f"Create it in NetBox first."
        )

    def _passes_filters(self, feature, filters):
        for field, expected in filters.items():
            value = feature.get(field)
            if str(value).strip() != str(expected).strip():
                return False
        return True

    def _apply_field_spec(self, value, spec):
        """Apply a field specification to transform a source value."""
        if not isinstance(spec, dict):
            return value

        # Value mapping
        if 'map' in spec:
            str_value = str(value).strip() if value is not None else ''
            mapped = spec['map'].get(str_value)
            if mapped is not None:
                return mapped
            return spec.get('default')

        # Transform function
        if 'transform' in spec:
            transform_name = spec['transform']
            transform_fn = TRANSFORMS.get(transform_name)
            if not transform_fn:
                raise CommandError(f"Unknown transform: {transform_name}")
            return transform_fn(value)

        # Format template
        if 'format' in spec:
            try:
                return spec['format'].format(value=value)
            except (ValueError, KeyError):
                return str(value)

        return value

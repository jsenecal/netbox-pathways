"""Compute start_anchor / end_anchor for existing pathways.

Mirrors attachment.resolve_anchor() against historical models: the side's
structure, else the nearest structure that is the location or one of its
ancestors (walked through `parent`, since historical models carry no MPTT
helpers), else the structure representing the location's site. Geometry is
not touched; reanchor_pathways reports ends that would now snap elsewhere.
"""

from django.db import migrations


def backfill(apps, schema_editor):
    Pathway = apps.get_model("netbox_pathways", "Pathway")
    Structure = apps.get_model("netbox_pathways", "Structure")
    SiteGeometry = apps.get_model("netbox_pathways", "SiteGeometry")
    Location = apps.get_model("dcim", "Location")

    identity = dict(Structure.objects.filter(location__isnull=False).values_list("location_id", "pk"))
    site_structure = dict(SiteGeometry.objects.filter(structure__isnull=False).values_list("site_id", "structure_id"))
    locations = {
        pk: (parent_id, site_id)
        for pk, parent_id, site_id in Location.objects.values_list("pk", "parent_id", "site_id")
    }
    resolved = {}

    def location_anchor(location_id):
        if location_id not in resolved:
            current, site_id = location_id, locations[location_id][1]
            anchor = None
            while current is not None:
                if current in identity:
                    anchor = identity[current]
                    break
                current = locations[current][0]
            resolved[location_id] = anchor if anchor is not None else site_structure.get(site_id)
        return resolved[location_id]

    def side_anchor(structure_id, location_id):
        if structure_id is not None:
            return structure_id
        if location_id is not None:
            return location_anchor(location_id)
        return None

    rows = Pathway.objects.values_list(
        "pk", "start_structure_id", "start_location_id", "end_structure_id", "end_location_id"
    )
    for pk, start_structure, start_location, end_structure, end_location in rows.iterator():
        Pathway.objects.filter(pk=pk).update(
            start_anchor_id=side_anchor(start_structure, start_location),
            end_anchor_id=side_anchor(end_structure, end_location),
        )


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_pathways", "0025_pathway_anchors"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]

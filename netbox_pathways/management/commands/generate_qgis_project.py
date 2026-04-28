"""
Generate a QGIS project file (.qgs) pre-configured with GeoJSON API layers.

Usage:
    python manage.py generate_qgis_project --url https://netbox.example.com --token <api-token>
    python manage.py generate_qgis_project --url https://netbox.example.com --token <api-token> --output my_project.qgs
"""

import uuid
import xml.etree.ElementTree as ET
from xml.dom import minidom

from django.core.management.base import BaseCommand

GEO_LAYERS = [
    {
        "name": "Structures",
        "endpoint": "/api/plugins/pathways/geo/structures/",
        "geometry": "Point",
    },
    {
        "name": "Pathways (All)",
        "endpoint": "/api/plugins/pathways/geo/pathways/",
        "geometry": "LineString",
    },
    {
        "name": "Conduits",
        "endpoint": "/api/plugins/pathways/geo/conduits/",
        "geometry": "LineString",
    },
    {
        "name": "Aerial Spans",
        "endpoint": "/api/plugins/pathways/geo/aerial-spans/",
        "geometry": "LineString",
    },
    {
        "name": "Direct Buried",
        "endpoint": "/api/plugins/pathways/geo/direct-buried/",
        "geometry": "LineString",
    },
]


class Command(BaseCommand):
    help = "Generate a QGIS project file (.qgs) with GeoJSON API layers"

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            required=True,
            help="Base URL of the NetBox instance (e.g., https://netbox.example.com)",
        )
        parser.add_argument(
            "--token",
            required=True,
            help="NetBox API token for authentication",
        )
        parser.add_argument(
            "--output",
            default="netbox_pathways.qgs",
            help="Output file path (default: netbox_pathways.qgs)",
        )

    def handle(self, *args, **options):
        base_url = options["url"].rstrip("/")
        token = options["token"]
        output = options["output"]

        project = self._build_project(base_url, token)

        xml_str = ET.tostring(project, encoding="unicode")
        pretty = minidom.parseString(xml_str).toprettyxml(indent="  ", encoding="UTF-8")  # noqa: S318

        with open(output, "wb") as f:
            f.write(pretty)

        self.stdout.write(self.style.SUCCESS(f"QGIS project written to: {output}"))
        self.stdout.write(f"Layers: {len(GEO_LAYERS)}")
        self.stdout.write(f"Open in QGIS: File > Open Project > {output}")

    def _build_project(self, base_url, token):
        qgis = ET.Element(
            "qgis",
            attrib={
                "version": "3.34.0",
                "projectname": "NetBox Pathways",
            },
        )

        # Project title
        title = ET.SubElement(qgis, "title")
        title.text = "NetBox Pathways"

        # CRS — WGS84
        project_crs = ET.SubElement(qgis, "projectCrs")
        spatialrefsys = ET.SubElement(project_crs, "spatialrefsys")
        ET.SubElement(spatialrefsys, "authid").text = "EPSG:4326"

        # Project layers
        project_layers = ET.SubElement(qgis, "projectlayers")

        layer_ids = []
        for layer_def in GEO_LAYERS:
            layer_id = f"pathways_{layer_def['name'].lower().replace(' ', '_').replace('(', '').replace(')', '')}_{uuid.uuid4().hex[:8]}"
            layer_ids.append((layer_id, layer_def["name"]))

            url = f"{base_url}{layer_def['endpoint']}?format=json&limit=0"
            # QGIS GeoJSON URL source with auth header
            uri = f"url={url}&authcfg=&http-header:Authorization=Token {token}"

            maplayer = ET.SubElement(
                project_layers,
                "maplayer",
                attrib={
                    "geometry": layer_def["geometry"],
                    "type": "vector",
                },
            )
            ET.SubElement(maplayer, "id").text = layer_id
            ET.SubElement(maplayer, "layername").text = layer_def["name"]
            ET.SubElement(maplayer, "datasource").text = uri
            ET.SubElement(maplayer, "provider", attrib={"encoding": "UTF-8"}).text = "ogr"
            srs = ET.SubElement(maplayer, "srs")
            srs_inner = ET.SubElement(srs, "spatialrefsys")
            ET.SubElement(srs_inner, "authid").text = "EPSG:4326"

        # Layer tree (legend order)
        layer_tree_group = ET.SubElement(qgis, "layer-tree-group")
        for layer_id, layer_name in layer_ids:
            ET.SubElement(
                layer_tree_group,
                "layer-tree-layer",
                attrib={
                    "id": layer_id,
                    "name": layer_name,
                    "checked": "Qt::Checked",
                    "expanded": "1",
                },
            )

        return qgis

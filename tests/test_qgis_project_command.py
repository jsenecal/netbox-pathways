"""Smoke test for the generate_qgis_project management command.

The command is a documented user-facing feature (QGIS integration); this
pins that it produces a parseable project file wiring every GeoJSON layer
to the given instance with token auth.
"""

import xml.etree.ElementTree as ET

from django.core.management import call_command

from netbox_pathways.management.commands.generate_qgis_project import GEO_LAYERS


def test_generate_qgis_project_writes_all_layers_with_token_auth(tmp_path):
    out = tmp_path / "pathways.qgs"

    call_command(
        "generate_qgis_project",
        url="https://netbox.example.com/",
        token="SECRET-TOKEN",
        output=str(out),
    )

    content = out.read_text()
    ET.fromstring(content)  # noqa: S314 -- our own output, checking well-formedness

    for layer in GEO_LAYERS:
        # Trailing slash on --url must not double up in the endpoint URLs.
        assert f"https://netbox.example.com{layer['endpoint']}" in content
    assert "Token SECRET-TOKEN" in content
    assert "EPSG:4326" in content

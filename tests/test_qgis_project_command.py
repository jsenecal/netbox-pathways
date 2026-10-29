"""Smoke test for the generate_qgis_project management command.

The command is a documented user-facing feature (QGIS integration); this
pins that it produces a parseable project file wiring every GeoJSON layer
to the given instance with token auth, and that every layer points at an
endpoint the API actually serves.
"""

import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlsplit

from django.core.management import call_command
from django.urls import resolve

from netbox_pathways.management.commands.generate_qgis_project import GEO_LAYERS
from netbox_pathways.pathway_types import DRAWN_TYPES

# The plugin API is mounted here; resolving against the plugin's own API
# urlconf checks the endpoint exists without loading the UI urlconf.
API_PREFIX = "/api/plugins/pathways/"


def _datasource_urls(content):
    root = ET.fromstring(content)  # noqa: S314 -- our own output, checking well-formedness
    # A datasource is "url=<layer url>&authcfg=&http-header:..."; the layer
    # URL ends where the QGIS provider options begin.
    return [ds.text.removeprefix("url=").split("&authcfg=")[0] for ds in root.iter("datasource")]


def _generate(tmp_path, url):
    out = tmp_path / "pathways.qgs"
    call_command("generate_qgis_project", url=url, token="SECRET-TOKEN", output=str(out))
    return out.read_text()


def test_generate_qgis_project_writes_all_layers_with_token_auth(tmp_path):
    content = _generate(tmp_path, "https://netbox.example.com/")

    urls = _datasource_urls(content)
    assert len(urls) == len(GEO_LAYERS)
    for url in urls:
        # Trailing slash on --url must not double up in the endpoint URLs.
        assert url.startswith("https://netbox.example.com/api/plugins/pathways/geo/")
    assert "Token SECRET-TOKEN" in content
    assert "EPSG:4326" in content


def test_every_qgis_layer_resolves_to_a_geo_endpoint(tmp_path):
    """Layers must not point at the removed per-type geo endpoints, which 404."""
    layer_types = set()
    for url in _datasource_urls(_generate(tmp_path, "https://netbox.example.com")):
        parts = urlsplit(url)
        api_path = parts.path.removeprefix(API_PREFIX)
        assert api_path != parts.path, url
        assert resolve("/" + api_path, urlconf="netbox_pathways.api.urls").url_name.startswith("geo-"), url
        query = parse_qs(parts.query)
        assert query["format"] == ["json"], url
        if "pathway_type" in query:
            layer_types.update(query["pathway_type"])
            assert query["containers"] == ["true"], url

    # One per-type layer for each type the map draws, and no others.
    assert layer_types == DRAWN_TYPES

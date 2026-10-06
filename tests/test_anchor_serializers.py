"""The API exposes the structure each pathway end attaches to."""

import pytest
from dcim.models import Location, Site
from django.contrib.gis.db.models.functions import Transform
from rest_framework.test import APIRequestFactory

from netbox_pathways.api.geo import ConduitGeoSerializer
from netbox_pathways.api.serializers import ConduitSerializer
from netbox_pathways.models import Conduit, SiteGeometry
from tests.helpers import make_building, make_conduit, make_pole


@pytest.fixture
def room_conduit(db):
    site = Site.objects.create(name="AS-Site", slug="as-site")
    building = make_building("AS-B", 0, 0, size=50)
    SiteGeometry.objects.create(site=site, structure=building)
    room = Location.objects.create(name="AS-Room", slug="as-room", site=site)
    conduit = make_conduit([(50, 25), (200, 25)], start_location=room, end_structure=make_pole("AS-P9", 200, 25))
    return building, conduit


def test_rest_serializer_nests_the_resolved_anchor(room_conduit):
    building, conduit = room_conduit
    request = APIRequestFactory().get("/")
    data = ConduitSerializer(conduit, context={"request": request}).data
    assert data["start_anchor"]["id"] == building.pk


def test_geojson_properties_carry_anchor_ids(room_conduit):
    building, conduit = room_conduit
    # The geo viewsets annotate the WGS84 geometry; do the same here.
    feature = Conduit.objects.annotate(geo_4326=Transform("path", 4326)).get(pk=conduit.pk)
    assert ConduitGeoSerializer(feature).data["properties"]["start_anchor"] == building.pk

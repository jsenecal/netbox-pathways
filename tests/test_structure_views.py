"""A structure page's pathway tabs and connected-structures panel."""

import pytest
from django.contrib.gis.geos import LineString

from netbox_pathways.models import AerialSpan, ConduitBank, DirectBuried
from netbox_pathways.views import (
    StructureAerialSpansView,
    StructureConduitBanksView,
    StructureConduitsView,
    StructureDirectBuriedView,
    StructureView,
)
from tests.helpers import SRID, make_conduit, make_pole


@pytest.fixture
def poles(db):
    return make_pole("SV-S1", 0, 0), make_pole("SV-S2", 100, 0), make_pole("SV-S3", 0, 100)


def _line():
    return LineString((0, 0), (100, 0), srid=SRID)


@pytest.mark.parametrize(
    "view, build",
    [
        (StructureConduitBanksView, lambda a, b: ConduitBank(path=_line(), start_structure=a, end_structure=b).save()),
        (StructureConduitsView, lambda a, b: make_conduit([(0, 0), (100, 0)], start_structure=a, end_structure=b)),
        (StructureAerialSpansView, lambda a, b: AerialSpan(path=_line(), start_structure=a, end_structure=b).save()),
        (StructureDirectBuriedView, lambda a, b: DirectBuried(path=_line(), start_structure=a, end_structure=b).save()),
    ],
)
def test_tab_lists_and_counts_the_structures_pathways_of_that_type(poles, view, build):
    s1, s2, s3 = poles
    build(s1, s2)
    build(s2, s1)

    assert (view.tab.badge(s1), view.tab.badge(s3)) == (2, 0)
    assert len(view().get_children(None, s1)) == 2


def test_connected_structures_panel_lists_far_ends(poles):
    s1, s2, s3 = poles
    make_conduit([(0, 0), (100, 0)], start_structure=s1, end_structure=s2)
    make_conduit([(0, 100), (0, 0)], start_structure=s3, end_structure=s1)

    table = StructureView().get_extra_context(None, s1)["connected_structures_table"]

    assert set(table.data.data) == {s2, s3}

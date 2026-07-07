"""Tests for AerialSpan model -- plugin-owned behavior only."""

import pytest
from django.contrib.gis.geos import LineString

from netbox_pathways.geo import get_srid
from netbox_pathways.models import AerialSpan


def _make_span(**kwargs):
    """Build an unsaved AerialSpan with a valid path; tests don't need to persist."""
    return AerialSpan(
        label=kwargs.pop("label", "test-span"),
        path=LineString([(0.0, 0.0), (0.001, 0.001)], srid=get_srid()),
        **kwargs,
    )


def test_aerial_type_choices_include_opgw():
    """OPGW is selectable as an aerial type (issue #59)."""
    from netbox_pathways.choices import AerialTypeChoices

    assert "opgw" in AerialTypeChoices.values()


@pytest.mark.parametrize(
    "start, end, expected",
    [
        (8.0, 10.0, 9.0),
        (7.5, 7.5, 7.5),
        (5.0, None, 5.0),
        (None, 12.0, 12.0),
        (None, None, None),
    ],
)
def test_attachment_height_property_returns_mean_with_fallback(start, end, expected):
    span = _make_span(start_attachment_height=start, end_attachment_height=end)
    assert span.attachment_height == expected


from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.fixture
def migrate_to():
    """Migrate the netbox_pathways app to a specific migration target."""

    def _do(target_name):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([("netbox_pathways", target_name)])
        return MigrationExecutor(connection)

    return _do


@pytest.mark.django_db(transaction=True)
def test_forward_migration_copies_attachment_height_to_both_sides(migrate_to):
    pre = "0017_conduitbank_height_width"
    post = "0018_aerialspan_attachment_height_per_side"

    executor = migrate_to(pre)
    OldAerialSpan = executor.loader.project_state([("netbox_pathways", pre)]).apps.get_model(
        "netbox_pathways", "AerialSpan"
    )
    OldAerialSpan.objects.create(
        label="span-a",
        path=LineString([(0.0, 0.0), (0.001, 0.001)], srid=get_srid()),
        pathway_type="aerial",
        attachment_height=8.5,
    )
    OldAerialSpan.objects.create(
        label="span-b",
        path=LineString([(0.0, 0.0), (0.001, 0.001)], srid=get_srid()),
        pathway_type="aerial",
        attachment_height=None,
    )

    executor = migrate_to(post)
    NewAerialSpan = executor.loader.project_state([("netbox_pathways", post)]).apps.get_model(
        "netbox_pathways", "AerialSpan"
    )

    a = NewAerialSpan.objects.get(label="span-a")
    assert a.start_attachment_height == 8.5
    assert a.end_attachment_height == 8.5

    b = NewAerialSpan.objects.get(label="span-b")
    assert b.start_attachment_height is None
    assert b.end_attachment_height is None


@pytest.mark.django_db(transaction=True)
def test_reverse_migration_copies_start_attachment_height_back(migrate_to):
    pre = "0017_conduitbank_height_width"
    post = "0018_aerialspan_attachment_height_per_side"

    migrate_to(post)
    executor = MigrationExecutor(connection)
    PostAerialSpan = executor.loader.project_state([("netbox_pathways", post)]).apps.get_model(
        "netbox_pathways", "AerialSpan"
    )
    PostAerialSpan.objects.create(
        label="span-c",
        path=LineString([(0.0, 0.0), (0.001, 0.001)], srid=get_srid()),
        pathway_type="aerial",
        start_attachment_height=7.0,
        end_attachment_height=9.0,
    )

    executor = migrate_to(pre)
    PreAerialSpan = executor.loader.project_state([("netbox_pathways", pre)]).apps.get_model(
        "netbox_pathways", "AerialSpan"
    )
    c = PreAerialSpan.objects.get(label="span-c")
    assert c.attachment_height == 7.0


@pytest.fixture(autouse=True)
def _restore_head(request):
    """Re-migrate to the latest migration after any test in this module that touched migrations."""
    yield
    if request.node.get_closest_marker("django_db") and request.node.get_closest_marker("django_db").kwargs.get(
        "transaction"
    ):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        leaf_nodes = executor.loader.graph.leaf_nodes("netbox_pathways")
        if leaf_nodes:
            executor.migrate([leaf_nodes[0]])

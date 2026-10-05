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


# --- Straight-line rules: an aerial span hangs between two supports ---------

SRID = get_srid()


def _structure(name, geom):
    from netbox_pathways.models import Structure

    return Structure.objects.create(name=name, geometry=geom)


def _pole(name, x, y):
    from django.contrib.gis.geos import Point

    return _structure(name, Point(x, y, srid=SRID))


def _building(name, x0, y0, size=10):
    from django.contrib.gis.geos import Polygon

    ring = ((x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size), (x0, y0))
    return _structure(name, Polygon(ring, srid=SRID))


def _coords(span):
    return [(round(x, 6), round(y, 6)) for x, y in span.path.coords]


@pytest.mark.django_db
class TestAerialSpanStraightLine:
    def test_detached_end_is_rejected(self):
        from django.core.exceptions import ValidationError

        span = AerialSpan(
            start_structure=_pole("P1", 0, 0),
            path=LineString((0, 0), (50, 0), srid=SRID),
        )
        with pytest.raises(ValidationError) as exc:
            span.clean()
        assert "end_structure" in exc.value.message_dict

    def test_location_without_identity_structure_is_detached(self):
        from dcim.models import Location, Site
        from django.core.exceptions import ValidationError

        site = Site.objects.create(name="AS-Site", slug="as-site")
        loc = Location.objects.create(name="AS-Loc", slug="as-loc", site=site)
        span = AerialSpan(start_structure=_pole("P1", 0, 0), end_location=loc)
        with pytest.raises(ValidationError) as exc:
            span.clean()
        assert "end_structure" in exc.value.message_dict

    def test_location_identity_structure_counts_as_attached(self):
        from dcim.models import Location, Site

        site = Site.objects.create(name="AS-Site2", slug="as-site2")
        loc = Location.objects.create(name="AS-Loc2", slug="as-loc2", site=site)
        pole = _pole("P2", 40, 0)
        pole.location = loc
        pole.save()
        span = AerialSpan(start_structure=_pole("P1", 0, 0), end_location=loc)
        span.clean()
        assert _coords(span) == [(0.0, 0.0), (40.0, 0.0)]

    def test_intermediate_vertices_are_dropped(self):
        span = AerialSpan(
            start_structure=_pole("P1", 0, 0),
            end_structure=_pole("P2", 40, 0),
            path=LineString((0, 0), (10, 15), (30, -5), (40, 0), srid=SRID),
        )
        span.clean()
        assert _coords(span) == [(0.0, 0.0), (40.0, 0.0)]

    def test_pole_end_is_pinned_even_when_submitted_far_away(self):
        span = AerialSpan(
            start_structure=_pole("P1", 0, 0),
            end_structure=_pole("P2", 40, 0),
            path=LineString((0, 0), (40, 50), srid=SRID),
        )
        span.clean()
        assert _coords(span)[-1] == (40.0, 0.0)

    def test_building_end_lands_on_boundary_near_submitted_point(self):
        # Submitted landing on the south wall, 3 m from the corner.
        span = AerialSpan(
            start_structure=_pole("P1", 0, -40),
            end_structure=_building("B1", 0, 0),
            path=LineString((0, -40), (3, 0.4), srid=SRID),
        )
        span.clean()
        assert _coords(span)[-1] == (3.0, 0.0)

    def test_missing_path_lands_on_the_wall_facing_the_other_end(self):
        span = AerialSpan(
            start_structure=_building("B1", 0, 0),
            end_structure=_pole("P1", 60, 5),
        )
        span.clean()
        assert _coords(span) == [(10.0, 5.0), (60.0, 5.0)]

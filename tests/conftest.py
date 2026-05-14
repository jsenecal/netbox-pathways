import pytest
from django.contrib.auth import get_user_model

from netbox_pathways.registry import LayerDetail, LayerStyle, registry


@pytest.fixture
def admin_user(db):
    user_model = get_user_model()
    return user_model.objects.create_superuser(
        username="testadmin",
        password="testpass123",  # noqa: S106
    )


def build_cable_with_terminations(*, label, site, terminate_a=True, terminate_b=True):
    """Build a Cable with optional A-/B-side terminations rooted in `site`.

    Each side is wired to an Interface on a Device in `site`, which causes
    `CableTermination.cache_related_objects()` to populate `_site` from
    `termination.device.site` on save. Used by tests that exercise view
    helpers which resolve cable terminations to graph nodes.
    """
    from dcim.models import (
        Cable,
        CableTermination,
        Device,
        DeviceRole,
        DeviceType,
        Interface,
        Manufacturer,
    )
    from django.contrib.contenttypes.models import ContentType

    mfr, _ = Manufacturer.objects.get_or_create(name="RP-mfr", slug="rp-mfr")
    dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr,
        model="RP-dt",
        slug="rp-dt",
    )
    dr, _ = DeviceRole.objects.get_or_create(name="RP-dr", slug="rp-dr")

    cable = Cable.objects.create(label=label)
    iface_ct = ContentType.objects.get_for_model(Interface)

    if terminate_a:
        dev_a = Device.objects.create(
            name=f"{label}-devA",
            device_type=dt,
            role=dr,
            site=site,
        )
        iface_a = Interface.objects.create(name="eth0", device=dev_a, type="1000base-t")
        CableTermination.objects.create(
            cable=cable,
            cable_end="A",
            termination_type=iface_ct,
            termination_id=iface_a.pk,
        )
    if terminate_b:
        dev_b = Device.objects.create(
            name=f"{label}-devB",
            device_type=dt,
            role=dr,
            site=site,
        )
        iface_b = Interface.objects.create(name="eth0", device=dev_b, type="1000base-t")
        CableTermination.objects.create(
            cable=cable,
            cable_end="B",
            termination_type=iface_ct,
            termination_id=iface_b.pk,
        )

    return cable


@pytest.fixture(autouse=True)
def _clean_registry():
    """Ensure each test starts with a clean registry."""
    registry.clear()
    yield
    registry.clear()


@pytest.fixture()
def url_layer_kwargs():
    return {
        "name": "test_cables",
        "label": "Test Cables",
        "geometry_type": "LineString",
        "source": "url",
        "url": "/api/plugins/test/geo/cables/",
        "style": LayerStyle(color="#e65100", dash="10 5"),
    }


@pytest.fixture()
def ref_layer_kwargs():
    return {
        "name": "test_points",
        "label": "Test Points",
        "geometry_type": "Point",
        "source": "reference",
        "queryset": lambda request: None,  # stub
        "geometry_field": "structure",
        "style": LayerStyle(color="#2e7d32", icon="mdi-circle"),
        "detail": LayerDetail(
            url_template="/api/plugins/test/points/{id}/",
            fields=["name", "status"],
        ),
    }

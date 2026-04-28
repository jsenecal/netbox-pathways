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

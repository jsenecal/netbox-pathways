"""NetBox resolves plugin filter forms and filtersets by module path.

`netbox/views/htmx.py:45-57` (ObjectSelectorView) does
`import_string(f"{app_label}.forms.{Model}FilterForm")` and
`import_string(f"{app_label}.filtersets.{Model}FilterSet")`. A model whose
paths do not resolve makes every `selector=True` field targeting it return a
500 -- the modal opens on a grey backdrop with no content. See issue #106.
"""

import pytest
from django.apps import apps
from django.utils.module_loading import import_string

PLUGIN_MODELS = sorted(model.__name__ for model in apps.get_app_config("netbox_pathways").get_models())


@pytest.mark.parametrize("model_name", PLUGIN_MODELS)
def test_filter_form_is_importable_from_forms(model_name):
    import_string(f"netbox_pathways.forms.{model_name}FilterForm")


@pytest.mark.parametrize("model_name", PLUGIN_MODELS)
def test_filterset_is_importable_from_filtersets(model_name):
    import_string(f"netbox_pathways.filtersets.{model_name}FilterSet")

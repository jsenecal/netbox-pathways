"""Import canary for the GraphQL filters module.

Strawberry resolves the filter classes lazily (via Annotated forward
references), so nothing imports ``graphql/filters.py`` at startup. A broken
declaration in it would pass Django's system checks and every other test,
then 500 on the first filtered GraphQL query. Importing it here keeps that
failure mode in the suite; anything past a clean import is framework.
"""


def test_graphql_filters_module_imports_cleanly():
    from netbox_pathways.graphql import filters

    assert filters.__all__

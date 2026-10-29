"""netbox-branching support.

netbox-branching only replicates models it recognises as branchable. The
auto-created through table of the symmetric ``CableSegment.lashed_with``
many-to-many is not a NetBox model, so branching cannot classify it on its
own and branch provisioning fails on it. The resolver below claims that one
table and leaves every other model to branching's default rules.
"""

LASHED_WITH_THROUGH = "netbox_pathways.cablesegment_lashed_with"


def lashed_with_resolver(model):
    """Return True for the lashed_with through table, None (no opinion) otherwise."""
    if model._meta.label_lower == LASHED_WITH_THROUGH:
        return True
    return None


def register_branching_resolvers():
    """Register the plugin's resolvers when netbox-branching is installed."""
    try:
        from netbox_branching.utilities import register_branching_resolver
    except ImportError:
        return
    register_branching_resolver(lashed_with_resolver)

from django.urls import reverse_lazy
from django.utils.text import format_lazy
from netbox.choices import ButtonColorChoices
from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem

from .choices import PathwayTypeChoices

# Menu labels for the pathway types whose plural is not the label plus "s".
_TYPE_PLURALS = {"direct_buried": "Direct Buried", "submarine": "Submarine"}


def _model_buttons(model_name):
    """Add + Import buttons for a model's list menu item."""
    return (
        PluginMenuButton(
            link=f"plugins:netbox_pathways:{model_name}_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            color=ButtonColorChoices.GREEN,
            permissions=[f"netbox_pathways.add_{model_name}"],
        ),
        PluginMenuButton(
            link=f"plugins:netbox_pathways:{model_name}_bulk_import",
            title="Import",
            icon_class="mdi mdi-upload",
            color=ButtonColorChoices.CYAN,
            permissions=[f"netbox_pathways.add_{model_name}"],
        ),
    )


def _with_type(link, pathway_type):
    """The URL of `link` preset to one pathway type."""
    return format_lazy("{}?pathway_type={}", reverse_lazy(link), pathway_type)


def _pathway_type_item(pathway_type, label):
    """A quick link opening the pathway list filtered to one type, with an add button for that type."""
    add = PluginMenuButton(
        link="plugins:netbox_pathways:pathway_add",
        title="Add",
        icon_class="mdi mdi-plus-thick",
        color=ButtonColorChoices.GREEN,
        permissions=["netbox_pathways.add_pathway"],
    )
    add.url = _with_type(add.link, pathway_type)
    item = PluginMenuItem(
        link="plugins:netbox_pathways:pathway_list",
        link_text=_TYPE_PLURALS.get(pathway_type, f"{label}s"),
        permissions=["netbox_pathways.view_pathway"],
        buttons=(add,),
    )
    item.url = _with_type(item.link, pathway_type)
    return item


menu = PluginMenu(
    label="Pathways",
    icon_class="mdi mdi-map-marker-path",
    groups=(
        (
            "Infrastructure",
            (
                PluginMenuItem(
                    link="plugins:netbox_pathways:structure_list",
                    link_text="Structures",
                    permissions=["netbox_pathways.view_structure"],
                    buttons=_model_buttons("structure"),
                ),
                PluginMenuItem(
                    link="plugins:netbox_pathways:pathway_list",
                    link_text="Pathways",
                    permissions=["netbox_pathways.view_pathway"],
                    buttons=_model_buttons("pathway"),
                ),
                PluginMenuItem(
                    link="plugins:netbox_pathways:conduitjunction_list",
                    link_text="Junctions",
                    permissions=["netbox_pathways.view_conduitjunction"],
                    buttons=_model_buttons("conduitjunction"),
                ),
            ),
        ),
        (
            "Pathway Types",
            tuple(_pathway_type_item(value, label) for value, label in dict(PathwayTypeChoices).items()),
        ),
        (
            "Cable Routing",
            (
                PluginMenuItem(
                    link="plugins:netbox_pathways:cablesegment_list",
                    link_text="Cable Segments",
                    permissions=["netbox_pathways.view_cablesegment"],
                    buttons=_model_buttons("cablesegment"),
                ),
                PluginMenuItem(
                    link="plugins:netbox_pathways:plannedroute_list",
                    link_text="Planned Routes",
                    permissions=["netbox_pathways.view_plannedroute"],
                    buttons=_model_buttons("plannedroute"),
                ),
                PluginMenuItem(
                    link="plugins:netbox_pathways:route_planner",
                    link_text="Route Planner",
                    permissions=["netbox_pathways.view_plannedroute"],
                ),
                PluginMenuItem(
                    link="plugins:netbox_pathways:pullsheet_list",
                    link_text="Pull Sheets",
                    permissions=["netbox_pathways.view_cablesegment"],
                ),
            ),
        ),
        (
            "GIS",
            (
                PluginMenuItem(
                    link="plugins:netbox_pathways:map",
                    link_text="Map",
                    permissions=["netbox_pathways.view_structure"],
                ),
                PluginMenuItem(
                    link="plugins:netbox_pathways:sitegeometry_list",
                    link_text="Site Geometries",
                    permissions=["netbox_pathways.view_sitegeometry"],
                    buttons=_model_buttons("sitegeometry"),
                ),
                PluginMenuItem(
                    link="plugins:netbox_pathways:circuitgeometry_list",
                    link_text="Circuit Routes",
                    permissions=["netbox_pathways.view_circuitgeometry"],
                    buttons=_model_buttons("circuitgeometry"),
                ),
            ),
        ),
    ),
)

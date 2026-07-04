from netbox.choices import ButtonColorChoices
from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem


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
                    link="plugins:netbox_pathways:conduit_list",
                    link_text="Conduits",
                    permissions=["netbox_pathways.view_conduit"],
                    buttons=_model_buttons("conduit"),
                ),
                PluginMenuItem(
                    link="plugins:netbox_pathways:aerialspan_list",
                    link_text="Aerial Spans",
                    permissions=["netbox_pathways.view_aerialspan"],
                    buttons=_model_buttons("aerialspan"),
                ),
                PluginMenuItem(
                    link="plugins:netbox_pathways:directburied_list",
                    link_text="Direct Buried",
                    permissions=["netbox_pathways.view_directburied"],
                    buttons=_model_buttons("directburied"),
                ),
                PluginMenuItem(
                    link="plugins:netbox_pathways:innerduct_list",
                    link_text="Innerducts",
                    permissions=["netbox_pathways.view_innerduct"],
                    buttons=_model_buttons("innerduct"),
                ),
                PluginMenuItem(
                    link="plugins:netbox_pathways:conduitbank_list",
                    link_text="Conduit Banks",
                    permissions=["netbox_pathways.view_conduitbank"],
                    buttons=_model_buttons("conduitbank"),
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

from netbox.choices import ButtonColorChoices
from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem

menu = PluginMenu(
    label='Pathways',
    icon_class='mdi mdi-map-marker-path',
    groups=(
        ('Infrastructure', (
            PluginMenuItem(
                link='plugins:netbox_pathways:structure_list',
                link_text='Structures',
                permissions=['netbox_pathways.view_structure'],
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_pathways:structure_add',
                        title='Add',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN,
                        permissions=['netbox_pathways.add_structure'],
                    ),
                    PluginMenuButton(
                        link='plugins:netbox_pathways:structure_import',
                        title='Import',
                        icon_class='mdi mdi-upload',
                        color=ButtonColorChoices.CYAN,
                        permissions=['netbox_pathways.add_structure'],
                    ),
                ),
            ),
            PluginMenuItem(
                link='plugins:netbox_pathways:conduit_list',
                link_text='Conduits',
                permissions=['netbox_pathways.view_conduit'],
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_pathways:conduit_add',
                        title='Add',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN,
                        permissions=['netbox_pathways.add_conduit'],
                    ),
                    PluginMenuButton(
                        link='plugins:netbox_pathways:conduit_import',
                        title='Import',
                        icon_class='mdi mdi-upload',
                        color=ButtonColorChoices.CYAN,
                        permissions=['netbox_pathways.add_conduit'],
                    ),
                ),
            ),
            PluginMenuItem(
                link='plugins:netbox_pathways:aerialspan_list',
                link_text='Aerial Spans',
                permissions=['netbox_pathways.view_aerialspan'],
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_pathways:aerialspan_add',
                        title='Add',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN,
                        permissions=['netbox_pathways.add_aerialspan'],
                    ),
                ),
            ),
            PluginMenuItem(
                link='plugins:netbox_pathways:directburied_list',
                link_text='Direct Buried',
                permissions=['netbox_pathways.view_directburied'],
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_pathways:directburied_add',
                        title='Add',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN,
                        permissions=['netbox_pathways.add_directburied'],
                    ),
                ),
            ),
            PluginMenuItem(
                link='plugins:netbox_pathways:innerduct_list',
                link_text='Innerducts',
                permissions=['netbox_pathways.view_innerduct'],
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_pathways:innerduct_add',
                        title='Add',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN,
                        permissions=['netbox_pathways.add_innerduct'],
                    ),
                ),
            ),
            PluginMenuItem(
                link='plugins:netbox_pathways:conduitbank_list',
                link_text='Conduit Banks',
                permissions=['netbox_pathways.view_conduitbank'],
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_pathways:conduitbank_add',
                        title='Add',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN,
                        permissions=['netbox_pathways.add_conduitbank'],
                    ),
                ),
            ),
            PluginMenuItem(
                link='plugins:netbox_pathways:conduitjunction_list',
                link_text='Junctions',
                permissions=['netbox_pathways.view_conduitjunction'],
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_pathways:conduitjunction_add',
                        title='Add',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN,
                        permissions=['netbox_pathways.add_conduitjunction'],
                    ),
                ),
            ),
        )),
        ('Cable Routing', (
            PluginMenuItem(
                link='plugins:netbox_pathways:cablesegment_list',
                link_text='Cable Segments',
                permissions=['netbox_pathways.view_cablesegment'],
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_pathways:cablesegment_add',
                        title='Add',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN,
                        permissions=['netbox_pathways.add_cablesegment'],
                    ),
                ),
            ),
            PluginMenuItem(
                link='plugins:netbox_pathways:slackloop_list',
                link_text='Slack Loops',
                permissions=['netbox_pathways.view_slackloop'],
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_pathways:slackloop_add',
                        title='Add',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN,
                        permissions=['netbox_pathways.add_slackloop'],
                    ),
                ),
            ),
            PluginMenuItem(
                link='plugins:netbox_pathways:plannedroute_list',
                link_text='Planned Routes',
                permissions=['netbox_pathways.view_plannedroute'],
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_pathways:plannedroute_add',
                        title='Add',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN,
                        permissions=['netbox_pathways.add_plannedroute'],
                    ),
                ),
            ),
            PluginMenuItem(
                link='plugins:netbox_pathways:pullsheet_list',
                link_text='Pull Sheets',
                permissions=['netbox_pathways.view_cablesegment'],
            ),
        )),
        ('GIS', (
            PluginMenuItem(
                link='plugins:netbox_pathways:map',
                link_text='Map',
                permissions=['netbox_pathways.view_structure'],
            ),
            PluginMenuItem(
                link='plugins:netbox_pathways:sitegeometry_list',
                link_text='Site Geometries',
                permissions=['netbox_pathways.view_sitegeometry'],
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_pathways:sitegeometry_add',
                        title='Add',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN,
                        permissions=['netbox_pathways.add_sitegeometry'],
                    ),
                ),
            ),
            PluginMenuItem(
                link='plugins:netbox_pathways:circuitgeometry_list',
                link_text='Circuit Routes',
                permissions=['netbox_pathways.view_circuitgeometry'],
                buttons=(
                    PluginMenuButton(
                        link='plugins:netbox_pathways:circuitgeometry_add',
                        title='Add',
                        icon_class='mdi mdi-plus-thick',
                        color=ButtonColorChoices.GREEN,
                        permissions=['netbox_pathways.add_circuitgeometry'],
                    ),
                ),
            ),
        )),
    ),
)

from netbox.choices import ButtonColorChoices
from netbox.plugins import PluginMenuButton, PluginMenuItem

menu_items = (
    PluginMenuItem(
        link='plugins:netbox_pathways:map',
        link_text='Map',
        permissions=['netbox_pathways.view_structure'],
    ),
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
    PluginMenuItem(
        link='plugins:netbox_pathways:pullsheet_list',
        link_text='Pull Sheets',
        permissions=['netbox_pathways.view_cablesegment'],
    ),
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
)

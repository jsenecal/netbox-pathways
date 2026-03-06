from netbox.plugins import PluginMenuButton, PluginMenuItem
from netbox.choices import ButtonColorChoices

menu_items = (
    PluginMenuItem(
        link='plugins:netbox_fiber:fiber_map',
        link_text='Fiber Map',
        permissions=['netbox_fiber.view_fiberstructure'],
        buttons=(
            PluginMenuButton(
                link='plugins:netbox_fiber:fiberstructure_add',
                title='Add Structure',
                icon_class='mdi mdi-plus-thick',
                color=ButtonColorChoices.GREEN,
                permissions=['netbox_fiber.add_fiberstructure']
            ),
            PluginMenuButton(
                link='plugins:netbox_fiber:fiberconduit_add',
                title='Add Conduit',
                icon_class='mdi mdi-plus-thick',
                color=ButtonColorChoices.BLUE,
                permissions=['netbox_fiber.add_fiberconduit']
            ),
        )
    ),
    PluginMenuItem(
        link='plugins:netbox_fiber:fiberstructure_list',
        link_text='Structures',
        permissions=['netbox_fiber.view_fiberstructure'],
        buttons=(
            PluginMenuButton(
                link='plugins:netbox_fiber:fiberstructure_add',
                title='Add',
                icon_class='mdi mdi-plus-thick',
                color=ButtonColorChoices.GREEN,
                permissions=['netbox_fiber.add_fiberstructure']
            ),
            PluginMenuButton(
                link='plugins:netbox_fiber:fiberstructure_import',
                title='Import',
                icon_class='mdi mdi-upload',
                color=ButtonColorChoices.CYAN,
                permissions=['netbox_fiber.add_fiberstructure']
            ),
        )
    ),
    PluginMenuItem(
        link='plugins:netbox_fiber:fiberconduit_list',
        link_text='Conduits',
        permissions=['netbox_fiber.view_fiberconduit'],
        buttons=(
            PluginMenuButton(
                link='plugins:netbox_fiber:fiberconduit_add',
                title='Add',
                icon_class='mdi mdi-plus-thick',
                color=ButtonColorChoices.GREEN,
                permissions=['netbox_fiber.add_fiberconduit']
            ),
            PluginMenuButton(
                link='plugins:netbox_fiber:fiberconduit_import',
                title='Import',
                icon_class='mdi mdi-upload',
                color=ButtonColorChoices.CYAN,
                permissions=['netbox_fiber.add_fiberconduit']
            ),
        )
    ),
)
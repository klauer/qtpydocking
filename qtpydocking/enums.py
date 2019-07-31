import enum
from collections import namedtuple

from qtpy.QtCore import Qt


class DockInsertParam(namedtuple('DockInsertParam', ('orientation',
                                                     'append'))):
    @property
    def insert_offset(self):
        return 1 if self.append else 0


class DockWidgetArea(enum.IntFlag):
    no_area = 0x00
    left = 0x01
    right = 0x02
    top = 0x04
    bottom = 0x08
    center = 0x10

    invalid = no_area
    outer_dock_areas = (top | left | right | bottom)
    all_dock_areas = (outer_dock_areas | center)


area_alignment = {
    DockWidgetArea.top: Qt.AlignHCenter | Qt.AlignBottom,
    DockWidgetArea.right: Qt.AlignLeft | Qt.AlignVCenter,
    DockWidgetArea.bottom: Qt.AlignHCenter | Qt.AlignTop,
    DockWidgetArea.left: Qt.AlignRight | Qt.AlignVCenter,
    DockWidgetArea.center: Qt.AlignCenter,

    DockWidgetArea.invalid: Qt.AlignCenter,
    DockWidgetArea.outer_dock_areas: Qt.AlignCenter,
    DockWidgetArea.all_dock_areas: Qt.AlignCenter,
}


class TitleBarButton(enum.Enum):
    tabs_menu = enum.auto()
    undock = enum.auto()
    close = enum.auto()


class DragState(enum.Enum):
    inactive = enum.auto()
    mouse_pressed = enum.auto()
    tab = enum.auto()
    floating_widget = enum.auto()


class InsertionOrder(enum.Enum):
    by_insertion = enum.auto()
    by_spelling = enum.auto()


class DockFlags(enum.IntFlag):
    '''
    These global configuration flags configure some global dock manager
    settings.
    '''
    # If this flag is set, the active tab in a tab area has a close button
    active_tab_has_close_button = 0x01
    # If the flag is set each dock area has a close button
    dock_area_has_close_button = 0x02
    # If the flag is set, the dock area close button closes the active tab, if
    # not set, it closes the complete cock area
    dock_area_close_button_closes_tab = 0x04
    # See QSplitter.setOpaqueResize() documentation
    opaque_splitter_resize = 0x08
    # If enabled, the XML writer automatically adds line-breaks and indentation
    # to empty sections between elements (ignorable whitespace).
    xml_auto_formatting = 0x10
    # If enabled, the XML output will be compressed and is not human readable
    # anymore
    xml_compression = 0x20
    # the default configuration
    default_config = (active_tab_has_close_button
                      | dock_area_has_close_button
                      | opaque_splitter_resize
                      | xml_auto_formatting
                      )


class OverlayMode(enum.Enum):
    dock_area = enum.auto()
    container = enum.auto()


class IconColor(enum.Enum):
    # the color of the frame of the small window icon
    frame_color = enum.auto()
    # the background color of the small window in the icon
    window_background_color = enum.auto()
    # the color that shows the overlay (the dock side) in the icon
    overlay_color = enum.auto()
    # the arrow that points into the direction
    arrow_color = enum.auto()
    # the color of the shadow rectangle that is painted below the icons
    shadow_color = enum.auto()


class DockWidgetFeature(enum.IntFlag):
    closable = 0x01
    movable = 0x02  # not yet implemented
    floatable = 0x04
    all_features = (closable | movable | floatable)
    no_features = 0


class WidgetState(enum.Enum):
    hidden = enum.auto()
    docked = enum.auto()
    floating = enum.auto()


class InsertMode(enum.Enum):
    '''
    Sets the widget for the dock widget to widget.

    The InsertMode defines how the widget is inserted into the dock widget.
    The content of a dock widget should be resizable do a very small size to
    prevent the dock widget from blocking the resizing. To ensure, that a dock
    widget can be resized very well, it is better to insert the content+ widget
    into a scroll area or to provide a widget that is already a scroll area or
    that contains a scroll area.

    If the InsertMode is AutoScrollArea, the DockWidget tries to automatically
    detect how to insert the given widget. If the widget is derived from
    QScrollArea (i.e. an QAbstractItemView), then the widget is inserted
    directly. If the given widget is not a scroll area, the widget will be
    inserted into a scroll area.

    To force insertion into a scroll area, you can also provide the InsertMode
    ForceScrollArea. To prevent insertion into a scroll area, you can provide
    the InsertMode ForceNoScrollArea
    '''
    auto_scroll_area = enum.auto()
    force_scroll_area = enum.auto()
    force_no_scroll_area = enum.auto()


class ToggleViewActionMode(enum.Enum):
    '''
    This mode configures the behavior of the toggle view action.

    If the mode if ActionModeToggle, then the toggle view action is a checkable
    action to show / hide the dock widget. If the mode is ActionModeShow, then
    the action is not checkable an it will always show the dock widget if
    clicked. If the mode is ActionModeShow, the user can only close the
    DockWidget with the close button.
    '''
    toggle = enum.auto()
    show = enum.auto()

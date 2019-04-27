# TODO: Q_PROPERTY

from .enums import DockInsertParam
from .enums import DockWidgetArea
from .enums import DockWidgetFeature
from .enums import TitleBarButton
from .enums import DockFlags
from .enums import DragState
from .enums import IconColor
from .enums import InsertMode
from .enums import OverlayMode
from .enums import WidgetState
from .enums import ToggleViewActionMode
from .enums import InsertionOrder
from .enums import XmlMode

from . import util

from .eliding_label import ElidingLabel
from .floating_dock_container import FloatingDockContainer
from .dock_area_layout import DockAreaLayout
from .dock_area_tab_bar import DockAreaTabBar
from .dock_area_title_bar import DockAreaTitleBar
from .dock_area_widget import DockAreaWidget
from .dock_container_widget import DockContainerWidget
from .dock_manager import DockManager
from .dock_overlay import DockOverlay, DockOverlayCross
from .dock_splitter import DockSplitter
from .dock_widget import DockWidget
from .dock_widget_tab import DockWidgetTab

from . import examples


__all__ = [
    'DockAreaLayout',
    'DockAreaTabBar',
    'DockAreaTitleBar',
    'DockAreaWidget',
    'DockContainerWidget',
    'DockInsertParam',
    'DockManager',
    'DockOverlay',
    'DockOverlayCross',
    'DockSplitter',
    'DockWidget',
    'DockWidgetArea',
    'DockWidgetFeature',
    'DockWidgetTab',
    'ElidingLabel',
    'FloatingDockContainer',
    'TitleBarButton',
    'DockFlags',
    'DragState',
    'IconColor',
    'InsertMode',
    'OverlayMode',
    'WidgetState',
    'ToggleViewActionMode',
    'InsertionOrder',
    'XmlMode',
    'examples'
]

from typing import TYPE_CHECKING, Optional
import logging

from qtpy.QtCore import QPoint, Qt, Signal, QSize
from qtpy.QtGui import QCursor
from qtpy.QtWidgets import (QAbstractButton, QAction, QBoxLayout, QFrame,
                            QMenu, QSizePolicy, QStyle, QToolButton)


from .enums import DockFlags, DragState, DockWidgetFeature, TitleBarButton
from .util import set_button_icon


if TYPE_CHECKING:
    from . import DockAreaWidget, DockAreaTabBar, DockManager


logger = logging.getLogger(__name__)


class DockAreaTitleBarPrivate:
    public: 'DockAreaTitleBar'
    tabs_menu_button: QToolButton
    undock_button: QToolButton
    close_button: QToolButton
    top_layout: QBoxLayout
    dock_area: 'DockAreaWidget'
    tab_bar: 'DockAreaTabBar'
    menu_outdated: bool
    tabs_menu: QMenu

    def __init__(self, public: 'DockAreaTitleBar'):
        self.public = public
        self.tabs_menu_button = None
        self.undock_button = None
        self.close_button = None
        self.top_layout = None
        self.dock_area = None
        self.tab_bar = None
        self.menu_outdated = True
        self.tabs_menu = None

    def create_buttons(self):
        '''
        Creates the title bar close and menu buttons
        '''
        self.tabs_menu_button = QToolButton()
        self.tabs_menu_button.setObjectName("tabsMenuButton")
        self.tabs_menu_button.setAutoRaise(True)
        self.tabs_menu_button.setPopupMode(QToolButton.InstantPopup)

        style = self.public.style()
        set_button_icon(style, self.tabs_menu_button, QStyle.SP_TitleBarUnshadeButton)

        self.tabs_menu = QMenu(self.tabs_menu_button)
        self.tabs_menu.setToolTipsVisible(True)
        self.tabs_menu.aboutToShow.connect(
            self.public.on_tabs_menu_about_to_show)
        self.tabs_menu_button.setMenu(self.tabs_menu)
        self.tabs_menu_button.setToolTip("List all tabs")

        self.tabs_menu_button.setSizePolicy(
            QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.top_layout.addWidget(self.tabs_menu_button, 0)
        self.tabs_menu_button.menu().triggered.connect(
            self.public.on_tabs_menu_action_triggered)

        # Undock button
        self.undock_button = QToolButton()
        self.undock_button.setObjectName("undockButton")
        self.undock_button.setAutoRaise(True)
        self.undock_button.setToolTip("Detach Group")

        set_button_icon(style, self.undock_button,
                        QStyle.SP_TitleBarNormalButton)

        self.undock_button.setSizePolicy(
            QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.top_layout.addWidget(self.undock_button, 0)
        self.undock_button.clicked.connect(
            self.public.on_undock_button_clicked)

        # Close button
        self.close_button = QToolButton()
        self.close_button.setObjectName("closeButton")
        self.close_button.setAutoRaise(True)

        set_button_icon(style, self.close_button, QStyle.SP_TitleBarCloseButton)

        if self.test_config_flag(DockFlags.dock_area_close_button_closes_tab):
            self.close_button.setToolTip("Close Active Tab")
        else:
            self.close_button.setToolTip("Close Group")

        self.close_button.setSizePolicy(
            QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.close_button.setIconSize(QSize(16, 16))
        self.top_layout.addWidget(self.close_button, 0)
        self.close_button.clicked.connect(self.public.on_close_button_clicked)

    def create_tab_bar(self):
        '''
        Creates the internal TabBar
        '''

        from .dock_area_tab_bar import DockAreaTabBar
        self.tab_bar = DockAreaTabBar(self.dock_area)
        self.top_layout.addWidget(self.tab_bar)

        self.tab_bar.tab_closed.connect(self.public.mark_tabs_menu_outdated)
        self.tab_bar.tab_opened.connect(self.public.mark_tabs_menu_outdated)
        self.tab_bar.tab_inserted.connect(self.public.mark_tabs_menu_outdated)
        self.tab_bar.removing_tab.connect(self.public.mark_tabs_menu_outdated)
        self.tab_bar.tab_moved.connect(self.public.mark_tabs_menu_outdated)
        self.tab_bar.current_changed.connect(self.public.on_current_tab_changed)
        self.tab_bar.tab_bar_clicked.connect(self.public.tab_bar_clicked)

        self.tab_bar.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tab_bar.customContextMenuRequested.connect(
            self.public.show_context_menu)

    def dock_manager(self) -> 'DockManager':
        '''
        Convenience function for DockManager access

        Returns
        -------
        value : DockManager
        '''
        return self.dock_area.dock_manager()

    def test_config_flag(self, flag: DockFlags) -> bool:
        '''
        Returns true if the given config flag is set

        Parameters
        ----------
        flag : DockFlags

        Returns
        -------
        value : bool
        '''
        return flag in self.dock_area.dock_manager().config_flags()


class DockAreaTitleBar(QFrame):
    # This signal is emitted if a tab in the tab bar is clicked by the user or
    # if the user clicks on a tab item in the title bar tab menu.
    tab_bar_clicked = Signal(int)

    def __init__(self, parent: 'DockAreaWidget'):
        '''
        Default Constructor

        Parameters
        ----------
        parent : DockAreaWidget
        '''
        super().__init__(parent)
        self.d = DockAreaTitleBarPrivate(self)
        self.d.dock_area = parent
        self.setObjectName("dockAreaTitleBar")

        self.d.top_layout = QBoxLayout(QBoxLayout.LeftToRight)
        self.d.top_layout.setContentsMargins(0, 0, 0, 0)
        self.d.top_layout.setSpacing(0)
        self.setLayout(self.d.top_layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.d.create_tab_bar()
        self.d.create_buttons()

    def __repr__(self):
        return f'<{self.__class__.__name__}>'

    def on_tabs_menu_about_to_show(self):
        if not self.d.menu_outdated:
            return

        menu = self.d.tabs_menu_button.menu()
        if menu is not None:
            menu.clear()

        for i in range(self.d.tab_bar.count()):
            if not self.d.tab_bar.is_tab_open(i):
                continue

            tab = self.d.tab_bar.tab(i)
            # TODO icon None?
            action = menu.addAction(tab.text())  # QAction(tab.icon(), tab.text()))
            action.setToolTip(tab.toolTip())
            action.setData(i)

        self.d.menu_outdated = False

    def on_close_button_clicked(self):
        logger.debug('DockAreaTitleBar.onCloseButtonClicked')
        if self.d.test_config_flag(DockFlags.dock_area_close_button_closes_tab):
            self.d.tab_bar.close_tab(self.d.tab_bar.current_index())
        else:
            self.d.dock_area.close_area()

    def on_undock_button_clicked(self):
        if self.d.dock_area.floatable:
            self.d.tab_bar.make_area_floating(
                self.mapFromGlobal(QCursor.pos()), DragState.inactive)

    def on_tabs_menu_action_triggered(self, action: QAction):
        '''
        On tabs menu action triggered

        Parameters
        ----------
        action : QAction
        '''
        index = action.data()
        self.d.tab_bar.set_current_index(index)
        self.tab_bar_clicked.emit(index)

    def on_current_tab_changed(self, index: int):
        '''
        On current tab changed

        Parameters
        ----------
        index : int
        '''
        if index < 0:
            return

        if self.d.test_config_flag(DockFlags.dock_area_close_button_closes_tab):
            dock_widget = self.d.tab_bar.tab(index).dock_widget()
            enabled = DockWidgetFeature.closable in dock_widget.features()
            self.d.close_button.setEnabled(enabled)

    def show_context_menu(self, pos: QPoint):
        '''
        Show context menu

        Parameters
        ----------
        pos : QPoint
        '''
        menu = QMenu(self)
        menu.addAction("Detach Area", self.on_undock_button_clicked)
        menu.addSeparator()
        action = menu.addAction("Close Area", self.on_close_button_clicked)
        action.setEnabled(self.d.dock_area.closable)

        menu.addAction("Close Other Areas", self.d.dock_area.close_other_areas)
        menu.exec_(self.mapToGlobal(pos))

    def mark_tabs_menu_outdated(self):
        self.d.menu_outdated = True

    def tab_bar(self) -> 'DockAreaTabBar':
        '''
        Returns the pointer to the tabBar

        Returns
        -------
        value : DockAreaTabBar
        '''
        return self.d.tab_bar

    def button(self, which: TitleBarButton) -> Optional[QAbstractButton]:
        '''
        Returns the button corresponding to the given title bar button identifier

        Parameters
        ----------
        which : TitleBarButton

        Returns
        -------
        value : QAbstractButton
        '''
        if which == TitleBarButton.tabs_menu:
            return self.d.tabs_menu_button
        if which == TitleBarButton.undock:
            return self.d.undock_button
        if which == TitleBarButton.close:
            return self.d.close_button

        return None

    def setVisible(self, visible: bool):
        '''
        This function is here for debug reasons

        Parameters
        ----------
        visible : bool
        '''
        super().setVisible(visible)
        self.mark_tabs_menu_outdated()

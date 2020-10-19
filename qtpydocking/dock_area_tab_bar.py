from typing import TYPE_CHECKING, Optional
import logging

from qtpy.QtCore import QEvent, QObject, QPoint, Qt, Signal
from qtpy.QtGui import QMouseEvent, QWheelEvent
from qtpy.QtWidgets import QBoxLayout, QFrame, QScrollArea, QSizePolicy, QWidget

from .util import start_drag_distance, event_filter_decorator
from .enums import DragState, DockWidgetArea
from .dock_widget_tab import DockWidgetTab
from .floating_dock_container import FloatingDockContainer


if TYPE_CHECKING:
    from . import DockAreaWidget


logger = logging.getLogger(__name__)


class DockAreaTabBarPrivate:
    public: 'DockAreaWidget'
    drag_start_mouse_pos: QPoint
    dock_area: 'DockAreaWidget'
    floating_widget: Optional['FloatingDockContainer']
    tabs_container_widget: QWidget
    tabs_layout: QBoxLayout
    current_index: int

    def __init__(self, public: 'DockAreaTabBar'):
        '''
        Private data for DockAreaTabBar

        Parameters
        ----------
        public : DockAreaTabBar
        '''
        self.public = public
        self.drag_start_mouse_pos = QPoint()
        self.dock_area = None
        self.floating_widget = None
        self.tabs_container_widget = None
        self.tabs_layout = None
        self.current_index = -1

    def update_tabs(self):
        '''
        Update tabs after current index changed or when tabs are removed. The
        function reassigns the stylesheet to update the tabs
        '''
        # Set active TAB and update all other tabs to be inactive
        for i in range(self.public.count()):
            tab_widget = self.public.tab(i)
            if not tab_widget:
                continue

            if i == self.current_index:
                tab_widget.show()
                tab_widget.set_active_tab(True)
                self.public.ensureWidgetVisible(tab_widget)
            else:
                tab_widget.set_active_tab(False)

    def connect_tab_signals(self, tab):
        tab.clicked.connect(self.public.on_tab_clicked)
        tab.close_requested.connect(self.public.on_tab_close_requested)
        tab.close_other_tabs_requested.connect(
            self.public.on_close_other_tabs_requested)
        tab.moved.connect(self.public.on_tab_widget_moved)

    def disconnect_tab_signals(self, tab):
        tab.clicked.disconnect(self.public.on_tab_clicked)
        tab.close_requested.disconnect(self.public.on_tab_close_requested)
        tab.close_other_tabs_requested.disconnect(
            self.public.on_close_other_tabs_requested)
        tab.moved.disconnect(self.public.on_tab_widget_moved)


class DockAreaTabBar(QScrollArea):
    # This signal is emitted when the tab bar's current tab is about to be
    # changed. The new current has the given index, or -1 if there isn't a new
    # one.
    current_changing = Signal(int)

    # This signal is emitted when the tab bar's current tab changes. The new
    # current has the given index, or -1 if there isn't a new one
    current_changed = Signal(int)

    # This signal is emitted when user clicks on a tab
    tab_bar_clicked = Signal(int)

    # This signal is emitted when the close button on a tab is clicked. The
    # index is the index that should be closed.
    tab_close_requested = Signal(int)

    # This signal is emitted if a tab has been closed
    tab_closed = Signal(int)

    # This signal is emitted if a tab has been opened. A tab is opened if it
    # has been made visible
    tab_opened = Signal(int)

    # This signal is emitted when the tab has moved the tab at index position
    tab_moved = Signal(int, int)

    # This signal is emitted, just before the tab with the given index is
    # removed
    removing_tab = Signal(int)

    # This signal is emitted if a tab has been inserted
    tab_inserted = Signal(int)

    def __init__(self, parent: 'DockAreaWidget'):
        '''
        Default Constructor

        Parameters
        ----------
        parent : DockAreaWidget
        '''
        super().__init__(parent)

        self.d = DockAreaTabBarPrivate(self)
        self.d.dock_area = parent

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        self.setFrameStyle(QFrame.NoFrame)
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.d.tabs_container_widget = QWidget()
        self.d.tabs_container_widget.setObjectName("tabsContainerWidget")
        self.setWidget(self.d.tabs_container_widget)

        self.d.tabs_layout = QBoxLayout(QBoxLayout.LeftToRight)
        self.d.tabs_layout.setContentsMargins(0, 0, 0, 0)
        self.d.tabs_layout.setSpacing(0)
        self.d.tabs_layout.addStretch(1)
        self.d.tabs_container_widget.setLayout(self.d.tabs_layout)

    def on_tab_clicked(self):
        tab = self.sender()
        if not tab or not isinstance(tab, DockWidgetTab):
            return

        index = self.d.tabs_layout.indexOf(tab)
        if index < 0:
            return

        self.set_current_index(index)
        self.tab_bar_clicked.emit(index)

    def on_tab_close_requested(self):
        tab = self.sender()
        index = self.d.tabs_layout.indexOf(tab)
        self.close_tab(index)

    def on_close_other_tabs_requested(self):
        sender = self.sender()

        for i in range(self.count()):
            tab = self.tab(i)
            if tab.is_closable() and not tab.isHidden() and tab != sender:
                self.close_tab(i)

    def on_tab_widget_moved(self, global_pos: QPoint):
        '''
        On tab widget moved

        Parameters
        ----------
        global_pos : QPoint
        '''
        moving_tab = self.sender()
        if not moving_tab or not isinstance(moving_tab, DockWidgetTab):
            return

        from_index = self.d.tabs_layout.indexOf(moving_tab)
        mouse_pos = self.mapFromGlobal(global_pos)
        to_index = -1

        # Find tab under mouse
        for i in range(self.count()):
            drop_tab = self.tab(i)
            if (drop_tab == moving_tab or not drop_tab.isVisibleTo(self) or
                    not drop_tab.geometry().contains(mouse_pos)):
                continue

            to_index = self.d.tabs_layout.indexOf(drop_tab)
            if to_index == from_index:
                to_index = -1
                continue
            elif to_index < 0:
                to_index = 0

            break

        # Now check if the mouse is behind the last tab
        if to_index < 0:
            if mouse_pos.x() > self.tab(self.count()-1).geometry().right():
                logger.debug('after all tabs')
                to_index = self.count()-1
            else:
                to_index = from_index

        self.d.tabs_layout.removeWidget(moving_tab)
        self.d.tabs_layout.insertWidget(to_index, moving_tab)
        if to_index >= 0:
            logger.debug('tabMoved from %s to %s', from_index, to_index)
            self.tab_moved.emit(from_index, to_index)
            self.set_current_index(to_index)

    def wheelEvent(self, event: QWheelEvent):
        '''
        Wheelevent

        Parameters
        ----------
        event : QWheelEvent
        '''
        event.accept()
        direction = event.angleDelta().y()
        horizontal_bar = self.horizontalScrollBar()
        delta = (20 if direction < 0
                 else -20)
        horizontal_bar.setValue(self.horizontalScrollBar().value() + delta)

    def mousePressEvent(self, ev: QMouseEvent):
        '''
        Stores mouse position to detect dragging

        Parameters
        ----------
        ev : QMouseEvent
        '''
        if ev.button() == Qt.LeftButton:
            ev.accept()
            self.d.drag_start_mouse_pos = ev.pos()
            return

        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev: QMouseEvent):
        '''
        Stores mouse position to detect dragging

        Parameters
        ----------
        ev : QMouseEvent
        '''
        if ev.button() != Qt.LeftButton:
            return super().mouseReleaseEvent(ev)

        logger.debug('DockAreaTabBar.mouseReleaseEvent')
        ev.accept()
        self.d.floating_widget = None
        self.d.drag_start_mouse_pos = QPoint()

    def mouseMoveEvent(self, ev: QMouseEvent):
        '''
        Starts floating the complete docking area including all dock widgets,
        if it is not the last dock area in a floating widget

        Parameters
        ----------
        ev : QMouseEvent
        '''
        super().mouseMoveEvent(ev)
        if ev.buttons() != Qt.LeftButton:
            return
        if self.d.floating_widget:
            self.d.floating_widget.move_floating()
            return

        # If this is the last dock area in a dock container it does not make
        # sense to move it to a new floating widget and leave this one empty
        container = self.d.dock_area.dock_container()
        if container.is_floating() and container.visible_dock_area_count() == 1:
            return

        # If one single dock widget in this area is not floatable, then the
        # whole area isn't floatable
        if not self.d.dock_area.floatable:
            return

        drag_distance = (self.d.drag_start_mouse_pos -
                         ev.pos()).manhattanLength()
        if drag_distance >= start_drag_distance():
            logger.debug('DockAreaTabBar.startFloating')
            self.start_floating(self.d.drag_start_mouse_pos)
            overlay = self.d.dock_area.dock_manager().container_overlay()
            overlay.set_allowed_areas(DockWidgetArea.outer_dock_areas)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        '''
        Double clicking the title bar also starts floating of the complete area

        Parameters
        ----------
        event : QMouseEvent
        '''
        # If this is the last dock area in a dock container it does not make
        # sense to move it to a new floating widget and leave this one empty
        container = self.d.dock_area.dock_container()
        if container.is_floating() and container.dock_area_count() == 1:
            return
        if not self.d.dock_area.floatable:
            return

        self.make_area_floating(event.pos(), DragState.inactive)

    def start_floating(self, offset: QPoint):
        '''
        Starts floating

        Parameters
        ----------
        offset : QPoint
        '''
        self.d.floating_widget = self.make_area_floating(
            offset, DragState.floating_widget)

    def make_area_floating(self, offset: QPoint,
                           drag_state: DragState) -> FloatingDockContainer:
        '''
        Makes the dock area floating

        Parameters
        ----------
        offset : QPoint
        drag_state : DragState

        Returns
        -------
        value : FloatingDockContainer
        '''
        size = self.d.dock_area.size()

        floating_widget = FloatingDockContainer(dock_area=self.d.dock_area)
        floating_widget.start_floating(offset, size, drag_state)
        top_level_dock_widget = floating_widget.top_level_dock_widget()
        if top_level_dock_widget is not None:
            top_level_dock_widget.emit_top_level_changed(True)

        return floating_widget

    def insert_tab(self, index: int, tab: 'DockWidgetTab'):
        '''
        Inserts the given dock widget tab at the given position. Inserting a
        new tab at an index less than or equal to the current index will
        increment the current index, but keep the current tab.

        Parameters
        ----------
        index : int
        tab : DockWidgetTab
        '''
        self.d.tabs_layout.insertWidget(index, tab)

        self.d.connect_tab_signals(tab)
        tab.installEventFilter(self)
        self.tab_inserted.emit(index)
        if index <= self.d.current_index:
            self.set_current_index(self.d.current_index+1)

    def remove_tab(self, tab: 'DockWidgetTab'):
        '''
        Removes the given DockWidgetTab from the tabbar

        Parameters
        ----------
        tab : DockWidgetTab
        '''
        if not self.count():
            return

        logger.debug('DockAreaTabBar.removeTab')
        new_current_index = self.current_index()
        remove_index = self.d.tabs_layout.indexOf(tab)
        if self.count() == 1:
            new_current_index = -1

        if new_current_index > remove_index:
            new_current_index -= 1
        elif new_current_index == remove_index:
            new_current_index = -1

            # First we walk to the right to search for the next visible tab
            for i in range(remove_index + 1, self.count()):
                if self.tab(i).isVisibleTo(self):
                    new_current_index = i-1
                    break

            # If there is no visible tab right to this tab then we walk to
            # the left to find a visible tab
            if new_current_index < 0:
                for i in range(remove_index - 1, -1, -1):
                    if self.tab(i).isVisibleTo(self):
                        new_current_index = i
                        break

        self.removing_tab.emit(remove_index)
        self.d.tabs_layout.removeWidget(tab)
        self.d.disconnect_tab_signals(tab)

        tab.removeEventFilter(self)
        logger.debug('NewCurrentIndex %s', new_current_index)

        if new_current_index != self.d.current_index:
            self.set_current_index(new_current_index)
        else:
            self.d.update_tabs()

    def count(self) -> int:
        '''
        Returns the number of tabs in this tabbar

        Returns
        -------
        value : int
        '''
        # The tab bar contains a stretch item as last item
        return self.d.tabs_layout.count() - 1

    def current_index(self) -> int:
        '''
        Returns the current index or -1 if no tab is selected

        Returns
        -------
        value : int
        '''
        return self.d.current_index

    def current_tab(self) -> Optional['DockWidgetTab']:
        '''
        Returns the current tab or a nullptr if no tab is selected.

        Returns
        -------
        value : DockWidgetTab
        '''
        if self.d.current_index < 0:
            return None
        return self.d.tabs_layout.itemAt(self.d.current_index).widget()

    def tab(self, index: int) -> Optional['DockWidgetTab']:
        '''
        Returns the tab with the given index

        Parameters
        ----------
        index : int

        Returns
        -------
        value : DockWidgetTab
        '''
        if index >= self.count() or index < 0:
            return None

        return self.d.tabs_layout.itemAt(index).widget()

    @event_filter_decorator
    def eventFilter(self, tab: QObject, event: QEvent) -> bool:
        '''
        Filters the tab widget events

        Parameters
        ----------
        tab : QObject
        event : QEvent

        Returns
        -------
        value : bool
        '''
        result = super().eventFilter(tab, event)
        if isinstance(tab, DockWidgetTab):
            if event.type() == QEvent.Hide:
                self.tab_closed.emit(self.d.tabs_layout.indexOf(tab))
            elif event.type() == QEvent.Show:
                self.tab_opened.emit(self.d.tabs_layout.indexOf(tab))

        return result

    def is_tab_open(self, index: int) -> bool:
        '''
        This function returns true if the tab is open, that means if it is
        visible to the user. If the function returns false, the tab is closed

        Parameters
        ----------
        index : int

        Returns
        -------
        value : bool
        '''
        if index < 0 or index >= self.count():
            return False

        return not self.tab(index).isHidden()

    def set_current_index(self, index: int):
        '''
        This property sets the index of the tab bar's visible tab

        Parameters
        ----------
        index : int
        '''
        if index == self.d.current_index:
            return
        if index < -1 or index > (self.count()-1):
            logger.warning('Invalid index %s', index)
            return

        self.current_changing.emit(index)
        self.d.current_index = index
        self.d.update_tabs()
        self.current_changed.emit(index)

    def close_tab(self, index: int):
        '''
        This function will close the tab given in Index param. Closing a tab
        means, the tab will be hidden, it will not be removed

        Parameters
        ----------
        index : int
        '''
        if index < 0 or index >= self.count():
            return

        tab = self.tab(index)
        if tab.isHidden():
            return

        self.tab_close_requested.emit(index)
        tab.hide()

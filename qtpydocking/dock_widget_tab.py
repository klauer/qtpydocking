from typing import TYPE_CHECKING, no_type_check
import logging

from qtpy.QtCore import QEvent, QPoint, QSize, Qt, Signal
from qtpy.QtGui import QContextMenuEvent, QCursor, QFontMetrics, QIcon, QMouseEvent
from qtpy.QtWidgets import (QBoxLayout, QFrame, QLabel, QMenu, QSizePolicy,
                            QStyle, QWidget, QPushButton)

from .util import start_drag_distance, set_button_icon
from .enums import DragState, DockFlags, DockWidgetArea, DockWidgetFeature
from .eliding_label import ElidingLabel

if TYPE_CHECKING:
    from . import (DockWidget, DockAreaWidget, FloatingDockContainer)

logger = logging.getLogger(__name__)


class DockWidgetTabPrivate:
    public: 'DockWidgetTab'
    dock_widget: 'DockWidget'
    icon_label: QLabel
    title_label: QLabel
    drag_start_mouse_position: QPoint
    is_active_tab: bool
    dock_area: 'DockAreaWidget'
    drag_state: DragState
    floating_widget: 'FloatingDockContainer'
    icon: QIcon
    close_button: QPushButton

    @no_type_check
    def __init__(self, public: 'DockWidgetTab'):
        '''
        Private data constructor

        Parameters
        ----------
        public : DockWidgetTab
        '''
        self.public = public
        self.dock_widget = None
        self.icon_label = None
        self.title_label = None
        self.drag_start_mouse_position = None
        self.is_active_tab = False
        self.dock_area = None
        self.drag_state = DragState.inactive
        self.floating_widget = None
        self.icon = None
        self.close_button = None

    def create_layout(self):
        '''
        Creates the complete layout including all controls
        '''
        self.title_label = ElidingLabel(text=self.dock_widget.windowTitle())
        self.title_label.set_elide_mode(Qt.ElideRight)
        self.title_label.setObjectName("dockWidgetTabLabel")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.close_button = QPushButton()
        self.close_button.setObjectName("tabCloseButton")

        set_button_icon(self.public.style(), self.close_button,
                        QStyle.SP_TitleBarCloseButton)

        self.close_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.close_button.setVisible(False)
        self.close_button.setToolTip("Close Tab")
        self.close_button.clicked.connect(self.public.close_requested)

        fm = QFontMetrics(self.title_label.font())
        spacing = round(fm.height()/4.0)

        # Fill the layout
        layout = QBoxLayout(QBoxLayout.LeftToRight)
        layout.setContentsMargins(2*spacing, 0, 0, 0)
        layout.setSpacing(0)
        self.public.setLayout(layout)
        layout.addWidget(self.title_label, 1)
        layout.addSpacing(spacing)
        layout.addWidget(self.close_button)
        layout.addSpacing(round(spacing*4.0/3.0))
        layout.setAlignment(Qt.AlignCenter)
        self.title_label.setVisible(True)

    def move_tab(self, ev: QMouseEvent):
        '''
        Moves the tab depending on the position in the given mouse event

        Parameters
        ----------
        ev : QMouseEvent
        '''
        ev.accept()
        # left, top, right, bottom = self.public.getContentsMargins()
        move_to_pos = self.public.mapToParent(ev.pos())-self.drag_start_mouse_position
        move_to_pos.setY(0)

        self.public.move(move_to_pos)
        self.public.raise_()

    def is_dragging_state(self, drag_state: DragState) -> bool:
        '''
        Test function for current drag state

        Parameters
        ----------
        drag_state : DragState

        Returns
        -------
        value : bool
        '''
        return self.drag_state == drag_state

    def title_area_geometry_contains(self, global_pos: QPoint) -> bool:
        '''
        Returns true if the given global point is inside the title area
        geometry rectangle. The position is given as global position.

        Parameters
        ----------
        global_pos : QPoint

        Returns
        -------
        value : bool
        '''
        return self.dock_area.title_bar_geometry().contains(self.dock_area.mapFromGlobal(global_pos))

    def start_floating(
            self,
            dragging_state: DragState = DragState.floating_widget
    ) -> bool:
        '''
        Starts floating of the dock widget that belongs to this title bar
        Returns true, if floating has been started and false if floating is not
        possible for any reason

        Parameters
        ----------
        dragging_state : DragState

        Returns
        -------
        value : bool
        '''
        dock_container = self.dock_widget.dock_container()
        if dock_container is None:
            return

        logger.debug('is_floating %s',
                     dock_container.is_floating())
        logger.debug('area_count %s',
                     dock_container.dock_area_count())
        logger.debug('widget_count %s',
                     self.dock_widget.dock_area_widget().dock_widgets_count())

        # if this is the last dock widget inside of this floating widget,
        # then it does not make any sense, to make it floating because
        # it is already floating
        if (dock_container.is_floating()
                and (dock_container.visible_dock_area_count() == 1)
                and (self.dock_widget.dock_area_widget().dock_widgets_count() == 1)):
            return False

        logger.debug('startFloating')
        self.drag_state = dragging_state
        size = self.dock_area.size()

        from .floating_dock_container import FloatingDockContainer

        if self.dock_area.dock_widgets_count() > 1:
            # If section widget has multiple tabs, we take only one tab
            self.floating_widget = FloatingDockContainer(dock_widget=self.dock_widget)
        else:
            # If section widget has only one content widget, we can move the complete
            # dock area into floating widget
            self.floating_widget = FloatingDockContainer(dock_area=self.dock_area)

        if dragging_state == DragState.floating_widget:
            self.floating_widget.start_dragging(self.drag_start_mouse_position,
                                                size, self.public)
            overlay = self.dock_widget.dock_manager().container_overlay()
            overlay.set_allowed_areas(DockWidgetArea.outer_dock_areas)
            self.floating_widget = self.floating_widget
        else:
            self.floating_widget.init_floating_geometry(self.drag_start_mouse_position, size)

        self.dock_widget.emit_top_level_changed(True)
        return True

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

    @property
    def floatable(self):
        '''
        Is the dock widget floatable?
        '''
        return DockWidgetFeature.floatable in self.dock_widget.features()


class DockWidgetTab(QFrame):
    active_tab_changed = Signal()
    clicked = Signal()
    close_requested = Signal()
    close_other_tabs_requested = Signal()
    moved = Signal(QPoint)

    def __init__(self, dock_widget: 'DockWidget', parent: QWidget):
        '''
        Parameters
        ----------
        dock_widget : DockWidget
            The dock widget this title bar
        parent : QWidget
            The parent widget of this title bar
        '''
        super().__init__(parent)
        self.d = DockWidgetTabPrivate(self)
        self.setAttribute(Qt.WA_NoMousePropagation, True)
        self.d.dock_widget = dock_widget
        self.d.create_layout()

    def on_detach_action_triggered(self):
        if self.d.floatable:
            self.d.drag_start_mouse_position = self.mapFromGlobal(QCursor.pos())
            self.d.start_floating(DragState.inactive)

    def mousePressEvent(self, ev: QMouseEvent):
        '''
        Mousepressevent

        Parameters
        ----------
        ev : QMouseEvent
        '''
        if ev.button() == Qt.LeftButton:
            ev.accept()
            self.d.drag_start_mouse_position = ev.pos()
            self.d.drag_state = DragState.mouse_pressed
            self.clicked.emit()
            return

        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev: QMouseEvent):
        '''
        Mouse release event

        Parameters
        ----------
        ev : QMouseEvent
        '''
        # End of tab moving, emit signal
        if self.d.is_dragging_state(DragState.tab) and self.d.dock_area:
            self.moved.emit(ev.globalPos())

        self.d.drag_start_mouse_position = QPoint()
        self.d.drag_state = DragState.inactive
        super().mouseReleaseEvent(ev)

    def mouseMoveEvent(self, ev: QMouseEvent):
        '''
        Mousemoveevent

        Parameters
        ----------
        ev : QMouseEvent
        '''
        if (not (ev.buttons() & Qt.LeftButton)
                or self.d.is_dragging_state(DragState.inactive)):
            self.d.drag_state = DragState.inactive
            return super().mouseMoveEvent(ev)

        # move floating window
        if self.d.is_dragging_state(DragState.floating_widget):
            self.d.floating_widget.move_floating()
            return super().mouseMoveEvent(ev)

        # move tab
        if self.d.is_dragging_state(DragState.tab):
            # Moving the tab is always allowed because it does not mean moving
            # the dock widget around
            self.d.move_tab(ev)

        # Maybe a fixed drag distance is better here ?
        drag_distance_y = abs(self.d.drag_start_mouse_position.y()-ev.pos().y())
        start_dist = start_drag_distance()
        if drag_distance_y >= start_dist:
            # If this is the last dock area in a dock container with only
            # one single dock widget it does not make  sense to move it to a new
            # floating widget and leave this one empty
            if (self.d.dock_area.dock_container().is_floating()
                    and self.d.dock_area.open_dock_widgets_count() == 1
                    and self.d.dock_area.dock_container().visible_dock_area_count() == 1):
                return


            # Floating is only allowed for widgets that are movable
            if self.d.floatable:
                self.d.start_floating()
        elif (self.d.dock_area.open_dock_widgets_count() > 1
              and (ev.pos()-self.d.drag_start_mouse_position).manhattanLength() >= start_dist):
            # Wait a few pixels before start moving
            self.d.drag_state = DragState.tab
        else:
            return super().mouseMoveEvent(ev)

    def contextMenuEvent(self, ev: QContextMenuEvent):
        '''
        Context menu event

        Parameters
        ----------
        ev : QContextMenuEvent
        '''
        ev.accept()
        self.d.drag_start_mouse_position = ev.pos()
        menu = QMenu(self)
        detach = menu.addAction("Detach", self.on_detach_action_triggered)
        detach.setEnabled(self.d.floatable)

        menu.addSeparator()

        action = menu.addAction("Close", self.close_requested)
        action.setEnabled(self.is_closable())
        menu.addAction("Close Others", self.close_other_tabs_requested)
        menu.exec(self.mapToGlobal(ev.pos()))

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        '''
        Double clicking the tab widget makes the assigned dock widget floating

        Parameters
        ----------
        event : QMouseEvent
        '''
        # If this is the last dock area in a dock container it does not make
        # sense to move it to a new floating widget and leave this one
        # empty
        if (self.d.floatable and
                (not self.d.dock_area.dock_container().is_floating()
                 or self.d.dock_area.dock_widgets_count() > 1)):
            self.d.drag_start_mouse_position = event.pos()
            self.d.start_floating(DragState.inactive)

        super().mouseDoubleClickEvent(event)

    def is_active_tab(self) -> bool:
        '''
        Returns true, if this is the active tab

        Returns
        -------
        value : bool
        '''
        return self.d.is_active_tab

    def set_active_tab(self, active: bool):
        '''
        Set this true to make this tab the active tab

        Parameters
        ----------
        active : bool
        '''
        closable = DockWidgetFeature.closable in self.d.dock_widget.features()
        tab_has_close_button = self.d.test_config_flag(DockFlags.active_tab_has_close_button)
        self.d.close_button.setVisible(active and closable and tab_has_close_button)
        if self.d.is_active_tab == active:
            return

        self.d.is_active_tab = active
        self.style().unpolish(self)
        self.style().polish(self)
        self.d.title_label.style().unpolish(self.d.title_label)
        self.d.title_label.style().polish(self.d.title_label)
        self.update()

        self.active_tab_changed.emit()

    def dock_widget(self) -> 'DockWidget':
        '''
        Returns the dock widget this title widget belongs to

        Returns
        -------
        value : DockWidget
        '''
        return self.d.dock_widget

    def set_dock_area_widget(self, dock_area: 'DockAreaWidget'):
        '''
        Sets the dock area widget the dockWidget returned by dockWidget() function belongs to.

        Parameters
        ----------
        dock_area : DockAreaWidget
        '''
        self.d.dock_area = dock_area

    def dock_area_widget(self) -> 'DockAreaWidget':
        '''
        Returns the dock area widget this title bar belongs to.

        Returns
        -------
        value : DockAreaWidget
        '''
        return self.d.dock_area

    def set_icon(self, icon: QIcon):
        '''
        Sets the icon to show in title bar

        Parameters
        ----------
        icon : QIcon
        '''
        layout = self.layout()
        if not self.d.icon_label and icon.isNull():
            return

        if not self.d.icon_label:
            self.d.icon_label = QLabel()
            self.d.icon_label.setAlignment(Qt.AlignVCenter)
            self.d.icon_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            self.d.icon_label.setToolTip(self.d.title_label.toolTip())
            layout.insertWidget(0, self.d.icon_label, Qt.AlignVCenter)
            layout.insertSpacing(1, round(1.5*layout.contentsMargins().left()/2.0))

        elif icon.isNull():
            # Remove icon label and spacer item
            layout.removeWidget(self.d.icon_label)
            layout.removeItem(layout.itemAt(0))
            self.d.icon_label.deleteLater()
            self.d.icon_label = None

        self.d.icon = icon
        if self.d.icon_label:
            self.d.icon_label.setPixmap(icon.pixmap(self.windowHandle(), QSize(16, 16)))
            self.d.icon_label.setVisible(True)

    def icon(self) -> QIcon:
        '''
        Returns the icon

        Returns
        -------
        value : QIcon
        '''
        return self.d.icon

    def text(self) -> str:
        '''
        Returns the tab text

        Returns
        -------
        value : str
        '''
        return self.d.title_label.text()

    def set_text(self, title: str):
        '''
        Sets the tab text

        Parameters
        ----------
        title : str
        '''
        self.d.title_label.setText(title)

    def is_closable(self) -> bool:
        '''
        This function returns true if the assigned dock widget is closeable

        Returns
        -------
        value : bool
        '''
        return (self.d.dock_widget and
                DockWidgetFeature.closable in self.d.dock_widget.features())

    def event(self, e: QEvent) -> bool:
        '''
        Track event ToolTipChange and set child ToolTip

        Parameters
        ----------
        e : QEvent

        Returns
        -------
        value : bool
        '''
        if e.type() == QEvent.ToolTipChange:
            text = self.toolTip()
            self.d.title_label.setToolTip(text)

        return super().event(e)

    # def setVisible(self, visible: bool):
    #     '''
    #     Set visible
    #
    #     Parameters
    #     ----------
    #     visible : bool
    #     '''
    #     super().setVisible(visible)

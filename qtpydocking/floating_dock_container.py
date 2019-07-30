from typing import TYPE_CHECKING
import logging

from qtpy.QtCore import (QEvent, QObject, QPoint, QRect, QSize, QXmlStreamReader, Qt)
from qtpy.QtGui import QCloseEvent, QCursor, QGuiApplication, QHideEvent, QMoveEvent
from qtpy.QtWidgets import QApplication, QBoxLayout, QWidget

from .enums import DockWidgetFeature, DragState, DockWidgetArea
from .util import QT_VERSION_TUPLE, event_filter_decorator
from .dock_container_widget import DockContainerWidget

if TYPE_CHECKING:
    from . import DockAreaWidget, DockWidget, DockManager


logger = logging.getLogger(__name__)

_z_order_counter = 0  # TODO


class FloatingDockContainerPrivate:
    public: 'FloatingDockContainer'
    dock_container: DockContainerWidget
    z_order_index: int
    dock_manager: 'DockManager'
    dragging_state: DragState
    drag_start_mouse_position: QPoint
    drop_container: DockContainerWidget
    single_dock_area: 'DockAreaWidget'

    def __init__(self, public):
        '''
        Private data constructor

        Parameters
        ----------
        public : FloatingDockContainer
        '''
        self.public = public
        self.dock_container = None

        global _z_order_counter  # TODO
        _z_order_counter += 1
        self.z_order_index = _z_order_counter

        self.dock_manager = None
        self.dragging_state = DragState.inactive
        self.drag_start_mouse_position = QPoint()
        self.drop_container = None
        self.single_dock_area = None

    def title_mouse_release_event(self):
        self.set_state(DragState.inactive)
        if not self.drop_container:
            return

        dock_manager = self.dock_manager
        dock_area_overlay = dock_manager.dock_area_overlay()
        container_overlay = dock_manager.container_overlay()
        if any(widget.drop_area_under_cursor() != DockWidgetArea.invalid
               for widget in (dock_area_overlay, container_overlay)):
            # Resize the floating widget to the size of the highlighted drop area
            # rectangle
            overlay = container_overlay
            if not overlay.drop_overlay_rect().isValid():
                overlay = dock_area_overlay

            rect = overlay.drop_overlay_rect()
            if rect.isValid():
                public = self.public
                frame_width = (public.frameSize().width() -
                               public.rect().width()) // 2
                title_bar_height = int(public.frameSize().height() -
                                       public.rect().height() - frame_width)

                top_left = overlay.mapToGlobal(rect.topLeft())
                top_left.setY(top_left.y() + title_bar_height)
                geom = QRect(top_left, QSize(rect.width(), rect.height() -
                                             title_bar_height))
                self.public.setGeometry(geom)
                qapp = QApplication.instance()
                qapp.processEvents()

            self.drop_container.drop_floating_widget(self.public, QCursor.pos())

        container_overlay.hide_overlay()
        dock_area_overlay.hide_overlay()

    def update_drop_overlays(self, global_pos: QPoint):
        '''
        Update drop overlays

        Parameters
        ----------
        global_pos : QPoint
        '''
        if not self.public.isVisible() or not self.dock_manager:
            return

        top_container = None
        for container_widget in self.dock_manager.dock_containers():
            if not container_widget.isVisible():
                continue
            if self.dock_container is container_widget:
                continue

            mapped_pos = container_widget.mapFromGlobal(global_pos)
            if container_widget.rect().contains(mapped_pos):
                if not top_container or container_widget.is_in_front_of(top_container):
                    top_container = container_widget

        self.drop_container = top_container
        container_overlay = self.dock_manager.container_overlay()
        dock_area_overlay = self.dock_manager.dock_area_overlay()
        if not top_container:
            container_overlay.hide_overlay()
            dock_area_overlay.hide_overlay()
            return

        visible_dock_areas = top_container.visible_dock_area_count()
        container_overlay.set_allowed_areas(
            DockWidgetArea.outer_dock_areas
            if visible_dock_areas > 1
            else DockWidgetArea.all_dock_areas
        )

        container_area = container_overlay.show_overlay(top_container)
        container_overlay.enable_drop_preview(container_area != DockWidgetArea.invalid)
        dock_area = top_container.dock_area_at(global_pos)

        if dock_area and dock_area.isVisible() and visible_dock_areas > 0:
            dock_area_overlay.enable_drop_preview(True)
            dock_area_overlay.set_allowed_areas(
                DockWidgetArea.no_area
                if visible_dock_areas == 1
                else DockWidgetArea.all_dock_areas)
            area = dock_area_overlay.show_overlay(dock_area)

            # A CenterDockWidgetArea for the dockAreaOverlay() indicates that
            # the mouse is in the title bar. If the ContainerArea is valid
            # then we ignore the dock area of the dockAreaOverlay() and disable
            # the drop preview
            if (area == DockWidgetArea.center and
                    container_area != DockWidgetArea.invalid):
                dock_area_overlay.enable_drop_preview(False)
                container_overlay.enable_drop_preview(True)
            else:
                container_overlay.enable_drop_preview(DockWidgetArea.invalid == area)
        else:
            dock_area_overlay.hide_overlay()

    def set_state(self, state_id: DragState):
        '''
        Set state

        Parameters
        ----------
        state_id : DragState
        '''
        self.dragging_state = state_id


class FloatingDockContainer(QWidget):
    def __init__(self, *, dock_area: 'DockAreaWidget' = None,
                 dock_widget: 'DockWidget' = None,
                 dock_manager: 'DockManager' = None):
        '''
        Parameters
        ----------
        dock_manager : DockManager

        dock_area : DockAreaWidget
            Create floating widget with the given dock area
        '''
        if dock_manager is None:
            if dock_area is not None:
                dock_manager = dock_area.dock_manager()
            elif dock_widget is not None:
                dock_manager = dock_widget.dock_manager()

        if dock_manager is None:
            raise ValueError('Must pass in either dock_area, dock_widget, or dock_manager')

        super().__init__(dock_manager, Qt.Window)
        self.d = FloatingDockContainerPrivate(self)
        self.setWindowFlags(Qt.Window | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.d.dock_manager = dock_manager
        layout = QBoxLayout(QBoxLayout.TopToBottom)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        dock_container = DockContainerWidget(dock_manager, self)
        self.d.dock_container = dock_container

        dock_container.destroyed.connect(self._destroyed)

        dock_container.dock_areas_added.connect(self.on_dock_areas_added_or_removed)
        dock_container.dock_areas_removed.connect(self.on_dock_areas_added_or_removed)
        layout.addWidget(dock_container)
        dock_manager.register_floating_widget(self)

        # We install an event filter to detect mouse release events because we
        # do not receive mouse release event if the floating widget is behind
        # the drop overlay cross
        qapp = QApplication.instance()
        qapp.installEventFilter(self)
        if dock_area is not None:
            dock_container.add_dock_area(dock_area)
        elif dock_widget is not None:
            dock_container.add_dock_widget(
                DockWidgetArea.center, dock_widget)

    def __repr__(self):
        return f'<FloatingDockContainer container={self.d.dock_container}>'

    def _destroyed(self):
        # TODO
        dock_container = self.d.dock_container
        self.d.dock_container = None
        if dock_container is not None:
            self.d.dock_manager.remove_dock_container(dock_container)
            self.d.dock_manager.remove_floating_widget(self)

        qapp = QApplication.instance()
        qapp.removeEventFilter(self)

    def deleteLater(self):
        self._destroyed()
        super().deleteLater()

    def on_dock_areas_added_or_removed(self):
        logger.debug('FloatingDockContainer.onDockAreasAddedOrRemoved()')
        top_level_dock_area = self.d.dock_container.top_level_dock_area()
        if top_level_dock_area is not None:
            self.d.single_dock_area = top_level_dock_area
            self.setWindowTitle(self.d.single_dock_area.current_dock_widget().windowTitle())
            self.d.single_dock_area.current_changed.connect(self.on_dock_area_current_changed)
        else:
            if self.d.single_dock_area:
                self.d.single_dock_area.current_changed.disconnect(self.on_dock_area_current_changed)
                self.d.single_dock_area = None

            self.setWindowTitle(QApplication.applicationDisplayName())

    def on_dock_area_current_changed(self, index: int):
        '''
        On dock area current changed

        Parameters
        ----------
        index : int
            Unused
        '''
        #pylint: disable=unused-argument
        widget = self.d.single_dock_area.current_dock_widget()
        if widget:
            self.setWindowTitle(widget.windowTitle())

    def start_floating(self, drag_start_mouse_pos: QPoint, size: QSize,
                       drag_state: DragState):
        '''
        Starts floating at the given global position. Use moveToGlobalPos() to
        move the widget to a new position depending on the start position given
        in Pos parameter

        Parameters
        ----------
        drag_start_mouse_pos : QPoint
        size : QSize
        drag_state : DragState
        '''
        self.resize(size)
        self.d.set_state(drag_state)
        self.d.drag_start_mouse_position = drag_start_mouse_pos
        self.move_floating()
        self.show()

    def start_dragging(self, drag_start_mouse_pos: QPoint, size: QSize):
        '''
        Call this function to start dragging the floating widget

        Parameters
        ----------
        drag_start_mouse_pos : QPoint
        size : QSize
        '''
        self.start_floating(drag_start_mouse_pos, size,
                            DragState.floating_widget)

    def init_floating_geometry(self, drag_start_mouse_pos: QPoint, size: QSize):
        '''
        Call this function if you just want to initialize the position and size
        of the floating widget

        Parameters
        ----------
        drag_start_mouse_pos : QPoint
        size : QSize
        '''
        self.start_floating(drag_start_mouse_pos, size, DragState.inactive)

    def move_floating(self):
        '''
        Moves the widget to a new position relative to the position given when
        startFloating() was called
        '''
        border_size = (self.frameSize().width()-self.size().width())/2
        move_to_pos = QCursor.pos()-self.d.drag_start_mouse_position-QPoint(border_size, 0)
        self.move(move_to_pos)

    def restore_state(self, stream: QXmlStreamReader, testing: bool) -> bool:
        '''
        Restores the state from given stream. If Testing is true, the function
        only parses the data from the given stream but does not restore
        anything. You can use this check for faulty files before you start
        restoring the state

        Parameters
        ----------
        stream : QXmlStreamReader
        testing : bool

        Returns
        -------
        value : bool
        '''
        if not self.d.dock_container.restore_state(stream, testing):
            return False

        self.on_dock_areas_added_or_removed()
        return True

    def update_window_title(self):
        '''
        Call this function to update the window title
        '''
        top_level_dock_area = self.d.dock_container.top_level_dock_area()
        if top_level_dock_area is not None:
            self.setWindowTitle(top_level_dock_area.current_dock_widget().windowTitle())
        else:
            self.setWindowTitle(QApplication.applicationDisplayName())

    def changeEvent(self, event: QEvent):
        '''
        Changeevent

        Parameters
        ----------
        event : QEvent
        '''
        super().changeEvent(event)
        if (event.type() == QEvent.ActivationChange) and self.isActiveWindow():
            logger.debug('FloatingWidget.changeEvent QEvent.ActivationChange ')
            global _z_order_counter  # TODO
            _z_order_counter += 1
            self.d.z_order_index = _z_order_counter

    def moveEvent(self, event: QMoveEvent):
        '''
        Moveevent

        Parameters
        ----------
        event : QMoveEvent
        '''
        super().moveEvent(event)
        state = self.d.dragging_state
        if state == DragState.mouse_pressed:
            self.d.set_state(DragState.floating_widget)
            self.d.update_drop_overlays(QCursor.pos())
        elif state == DragState.floating_widget:
            self.d.update_drop_overlays(QCursor.pos())

    def event(self, e: QEvent) -> bool:
        '''
        Event

        Parameters
        ----------
        e : QEvent

        Returns
        -------
        value : bool
        '''
        state = self.d.dragging_state
        if state == DragState.inactive:
            # Normally we would check here, if the left mouse button is pressed.
            # But from QT version 5.12.2 on the mouse events from
            # QEvent.NonClientAreaMouseButtonPress return the wrong mouse
            # button The event always returns Qt.RightButton even if the left
            # button is clicked.
            if e.type() == QEvent.NonClientAreaMouseButtonPress:
                if QT_VERSION_TUPLE >= (5, 12, 2):
                    # and QGuiApplication.mouseButtons().testFlag(Qt.LeftButton ...
                    logger.debug('FloatingWidget.event Event.NonClientAreaMouseButtonPress %s', e.type())
                    self.d.set_state(DragState.mouse_pressed)
                elif QGuiApplication.mouseButtons() == Qt.LeftButton:
                    logger.debug('FloatingWidget.event Event.NonClientAreaMouseButtonPress %s', e.type())
                    self.d.set_state(DragState.mouse_pressed)
        elif state == DragState.mouse_pressed:
            if e.type() == QEvent.NonClientAreaMouseButtonDblClick:
                logger.debug('FloatingWidget.event QEvent.NonClientAreaMouseButtonDblClick')
                self.d.set_state(DragState.inactive)
            elif e.type() == QEvent.Resize:
                # If the first event after the mouse press is a resize event, then
                # the user resizes the window instead of dragging it around.
                # But there is one exception. If the window is maximized,
                # then dragging the window via title bar will cause the widget to
                # leave the maximized state. This in turn will trigger a resize event.
                # To know, if the resize event was triggered by user via moving a
                # corner of the window frame or if it was caused by a windows state
                # change, we check, if we are not in maximized state.
                if not self.isMaximized():
                    self.d.set_state(DragState.inactive)
        elif state == DragState.floating_widget:
            if e.type() == QEvent.NonClientAreaMouseButtonRelease:
                logger.debug('FloatingWidget.event QEvent.NonClientAreaMouseButtonRelease')
                self.d.title_mouse_release_event()

        return super().event(e)

    def closeEvent(self, event: QCloseEvent):
        '''
        Closeevent

        Parameters
        ----------
        event : QCloseEvent
        '''
        logger.debug('FloatingDockContainer closeEvent')
        self.d.set_state(DragState.inactive)
        if not self.is_closable():
            event.ignore()
            return

        # In Qt version after 5.9.2 there seems to be a bug that causes the
        # QWidget.event() function to not receive any NonClientArea mouse
        # events anymore after a close/show cycle. The bug is reported here:
        # https://bugreports.qt.io/browse/QTBUG-73295
        # The following code is a workaround for Qt versions > 5.9.2 that seems
        # to work
        # Starting from Qt version 5.12.2 this seems to work again. But
        # now the QEvent.NonClientAreaMouseButtonPress function returns always
        # Qt.RightButton even if the left button was pressed
        if (5, 9, 2) < QT_VERSION_TUPLE < (5, 12, 2):
            event.ignore()
            self.hide()
        else:
            super().closeEvent(event)

    def hideEvent(self, event: QHideEvent):
        '''
        Hideevent

        Parameters
        ----------
        event : QHideEvent
        '''
        super().hideEvent(event)
        for dock_area in self.d.dock_container.opened_dock_areas():
            for dock_widget in dock_area.opened_dock_widgets():
                dock_widget.toggle_view(False)

    # def showEvent(self, event: QShowEvent):
    #     '''
    #     Showevent
    #
    #     Parameters
    #     ----------
    #     event : QShowEvent
    #     '''
    #     super().showEvent(event)

    @event_filter_decorator
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        '''
        Eventfilter

        Parameters
        ----------
        watched : QObject
            Unused
        event : QEvent

        Returns
        -------
        value : bool
        '''
        #pylint: disable=unused-argument
        if event.type() == QEvent.MouseButtonRelease:
            logger.debug('MouseButtonRelease')
            if self.d.dragging_state == DragState.floating_widget:
                qapp = QApplication.instance()
                qapp.removeEventFilter(self)
                logger.debug('FloatingWidget.eventFilter QEvent.MouseButtonRelease')
                self.d.title_mouse_release_event()

        return False


    def dock_container(self) -> 'DockContainerWidget':
        '''
        Access function for the internal dock container

        Returns
        -------
        value : DockContainerWidget
        '''
        return self.d.dock_container

    def is_closable(self) -> bool:
        '''
        This function returns true, if it can be closed. It can be closed, if
        all dock widgets in all dock areas can be closed

        Returns
        -------
        value : bool
        '''
        return DockWidgetFeature.closable in self.d.dock_container.features()

    def has_top_level_dock_widget(self) -> bool:
        '''
        This function returns true, if this floating widget has only one single
        visible dock widget in a single visible dock area. The single dock
        widget is a real top level floating widget because no other widgets are
        docked.

        Returns
        -------
        value : bool
        '''
        return self.d.dock_container.has_top_level_dock_widget()

    def top_level_dock_widget(self) -> 'DockWidget':
        '''
        This function returns the first dock widget in the first dock area. If
        the function hasSingleDockWidget() returns true, then this function
        returns this single dock widget.

        Returns
        -------
        value : DockWidget
        '''
        return self.d.dock_container.top_level_dock_widget()

    def dock_widgets(self) -> list:
        '''
        This function returns a list of all dock widget in this floating
        widget. This is a simple convenience function that simply calls the
        dockWidgets() function of the internal container widget.

        Returns
        -------
        value : list
        '''
        return self.d.dock_container.dock_widgets()

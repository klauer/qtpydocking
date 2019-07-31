import logging
import pathlib

from typing import TYPE_CHECKING, Dict, List

from qtpy.QtCore import (QByteArray, QSettings, QXmlStreamReader,
                         QXmlStreamWriter, Signal)
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QAction, QMainWindow, QMenu, QWidget

from .enums import InsertionOrder, DockFlags, DockWidgetArea, OverlayMode

from .dock_container_widget import DockContainerWidget
from .dock_overlay import DockOverlay
from .floating_dock_container import FloatingDockContainer
from .util import LINUX

try:
    from qtpy.QtCore import qCompress, qUncompress
except ImportError:
    qCompress = None
    qUncompress = None


if TYPE_CHECKING:
    from .dock_area_widget import DockAreaWidget
    from .dock_widget import DockWidget


logger = logging.getLogger(__name__)


class DockManagerPrivate:
    public: 'DockManager'
    floating_widgets: List[FloatingDockContainer]
    containers: List['DockContainerWidget']
    container_overlay: DockOverlay
    dock_area_overlay: DockOverlay
    dock_widgets_map: Dict[str, 'DockWidget']
    perspectives: Dict[str, QByteArray]
    view_menu_groups: Dict[str, QMenu]
    view_menu: QMenu
    menu_insertion_order: InsertionOrder
    restoring_state: bool
    config_flags: DockFlags

    def __init__(self, public):
        '''
        Private data constructor

        Parameters
        ----------
        public : DockManager
        '''
        self.public = public
        self.floating_widgets = []
        self.containers = []
        self.container_overlay = None
        self.dock_area_overlay = None
        self.dock_widgets_map = {}
        self.perspectives = {}
        self.view_menu_groups = {}
        self.view_menu = None
        self.menu_insertion_order = InsertionOrder.by_spelling
        self.restoring_state = False
        self.config_flags = DockFlags.default_config

    def check_format(self, state: QByteArray, version: int) -> bool:
        '''
        Checks if the given data stream is a valid docking system state file.

        Parameters
        ----------
        state : QByteArray
        version : int

        Returns
        -------
        value : bool
        '''
        return self.restore_state_from_xml(state, version, testing=True)

    def restore_state_from_xml(self, state: QByteArray, version: int, testing: bool) -> bool:
        '''
        Restores the state

        Parameters
        ----------
        state : QByteArray
        version : int
        testing : bool

        Returns
        -------
        value : bool
        '''
        if state.isEmpty():
            return False

        stream = QXmlStreamReader(state)
        stream.readNextStartElement()
        if stream.name() != "QtAdvancedDockingSystem":
            return False

        v = stream.attributes().value("Version")
        if int(v) != version:
            return False

        result = True
        dock_containers = stream.attributes().value("Containers")
        logger.debug('dock_containers %s', dock_containers)
        dock_container_count = 0
        while stream.readNextStartElement():
            if stream.name() == "Container":
                result = self.restore_container(dock_container_count, stream,
                                                testing=testing)
                if not result:
                    break
                dock_container_count += 1

        if testing or not dock_container_count:
            return result

        # Delete remaining empty floating widgets
        floating_widget_index = dock_container_count - 1
        delete_count = len(self.floating_widgets) - floating_widget_index

        for i in range(delete_count):
            to_remove = self.floating_widgets[floating_widget_index + i]
            self.public.remove_dock_container(
                to_remove.dock_container()
            )
            to_remove.deleteLater()

        return result

    def restore_state(self, state: QByteArray, version: int) -> bool:
        '''
        Restore state

        Parameters
        ----------
        state : QByteArray
        version : int

        Returns
        -------
        value : bool
        '''
        if not self.check_format(state, version):
            logger.debug('checkFormat: Error checking format!')
            return False

        # Hide updates of floating widgets from use
        self.hide_floating_widgets()
        self.mark_dock_widgets_dirty()
        if not self.restore_state_from_xml(state, version, testing=False):
            logger.debug('restoreState: Error restoring state!')
            return False

        self.restore_dock_widgets_open_state()
        self.restore_dock_areas_indices()
        self.emit_top_level_events()
        return True

    def restore_dock_widgets_open_state(self):
        # All dock widgets, that have not been processed in the restore state
        # function are invisible to the user now and have no assigned dock area
        # They do not belong to any dock container, until the user toggles the
        # toggle view action the next time
        for dock_widget in self.dock_widgets_map.values():
            if dock_widget.property("dirty"):
                dock_widget.flag_as_unassigned()
            else:
                dock_widget.toggle_view_internal(
                    not dock_widget.property("closed")
                )

    def restore_dock_areas_indices(self):
        # Now all dock areas are properly restored and we setup the index of
        # The dock areas because the previous toggleView() action has changed
        # the dock area index
        for dock_container in self.containers:
            for i in range(dock_container.dock_area_count()):
                dock_area = dock_container.dock_area(i)
                dock_widget_name = dock_area.property("currentDockWidget")
                dock_widget = None
                if not dock_widget_name:
                    dock_widget = self.public.find_dock_widget(dock_widget_name)

                if not dock_widget or dock_widget.is_closed():
                    index = dock_area.index_of_first_open_dock_widget()
                    if index < 0:
                        continue

                    dock_area.set_current_index(index)

                else:
                    dock_area.internal_set_current_dock_widget(dock_widget)

    def emit_top_level_events(self):
        # Finally we need to send the topLevelChanged() signals for all dock
        # widgets if top level changed
        for dock_container in self.containers:
            top_level_dock_widget = dock_container.top_level_dock_widget()
            if top_level_dock_widget is not None:
                top_level_dock_widget.emit_top_level_changed(True)
            else:
                for i in range(dock_container.dock_area_count()):
                    dock_area = dock_container.dock_area(i)
                    for dock_widget in dock_area.dock_widgets():
                        dock_widget.emit_top_level_changed(False)

    def hide_floating_widgets(self):
        # Hide updates of floating widgets from use
        for floating_widget in self.floating_widgets:
            floating_widget.hide()

    def mark_dock_widgets_dirty(self):
        for dock_widget in self.dock_widgets_map.values():
            dock_widget.setProperty("dirty", True)

    def restore_container(self, index: int, stream: QXmlStreamReader,
                          testing: bool) -> bool:
        '''
        Restores the container with the given index

        Parameters
        ----------
        index : int
        stream : QXmlStreamReader
        testing : bool

        Returns
        -------
        value : bool
        '''
        if testing:
            index = 0

        if index >= len(self.containers):
            floating_widget = FloatingDockContainer(dock_manager=self.public)
            result = floating_widget.restore_state(stream, testing)
        else:
            logger.debug('containers[%d].restore_state()', index)
            container = self.containers[index]
            if container.is_floating():
                result = container.floating_widget().restore_state(stream, testing)
            else:
                result = DockContainerWidget.restore_state(container, stream,
                                                           testing)

        return result

    def load_stylesheet(self, fn=None):
        '''
        Loads the stylesheet
        '''
        if fn is None:
            fn = self.public.default_style_sheet

        with open(fn, 'rt') as f:
            stylesheet = f.read()

        self.public.setStyleSheet(stylesheet)

    def add_action_to_menu(self, action: QAction, menu: QMenu, insert_sorted: bool):
        '''
        Adds action to menu - optionally in sorted order

        Parameters
        ----------
        action : QAction
        menu : QMenu
        insert_sorted : bool
        '''
        if insert_sorted:
            actions = menu.actions()
            if not actions:
                menu.addAction(action)
            else:
                actions = [act.text() for act in actions] + [action.text()]
                actions.sort()
                menu.insertAction(actions.index(action.text()), action)
        else:
            menu.addAction(action)


class DockManager(DockContainerWidget):
    default_style_sheet = pathlib.Path(__file__).parent / (
            'default_linux.css' if LINUX else 'default.css')

    # This signal is emitted if the list of perspectives changed
    perspective_list_changed = Signal()

    # This signal is emitted if perspectives have been removed
    perspectives_removed = Signal()

    # This signal is emitted, if the restore function is called, just before
    # the dock manager starts restoring the state. If this function is called,
    # nothing has changed yet
    restoring_state = Signal()

    # This signal is emitted if the state changed in restoreState. The signal
    # is emitted if the restoreState() function is called or if the
    # openPerspective() function is called
    state_restored = Signal()

    # This signal is emitted, if the dock manager starts opening a perspective.
    # Opening a perspective may take more than a second if there are many complex
    # widgets. The application may use this signal to show some progress
    # indicator or to change the mouse cursor into a busy cursor.
    opening_perspective = Signal(str)

    # This signal is emitted if the dock manager finished opening a perspective
    perspective_opened = Signal(str)

    def __init__(self, parent: QWidget):
        '''
        The central dock manager that maintains the complete docking system.
        With the configuration flags you can globally control the functionality
        of the docking system.

        If the given parent is a QMainWindow, the dock manager sets itself as
        the central widget. Before you create any dock widgets, you should
        properly setup the configuration flags via setConfigFlags()

        Parameters
        ----------
        parent : QWidget
        '''
        super().__init__(self, parent)
        self._mgr = DockManagerPrivate(self)
        self.create_root_splitter()
        if isinstance(parent, QMainWindow):
            parent.setCentralWidget(self)

        self._mgr.view_menu = QMenu("Show View", self)
        self._mgr.dock_area_overlay = DockOverlay(self, OverlayMode.dock_area)
        self._mgr.container_overlay = DockOverlay(self, OverlayMode.container)
        self._mgr.containers.append(self)
        self._mgr.load_stylesheet()

    def deleteLater(self):
        floating_widgets = self._mgr.floating_widgets
        for floating_widget in floating_widgets:
            floating_widget.deleteLater()
        self._mgr.floating_widgets.clear()
        super().deleteLater()

    def register_floating_widget(self, floating_widget: FloatingDockContainer):
        '''
        Registers the given floating widget in the internal list of floating widgets

        Parameters
        ----------
        floating_widget : FloatingDockContainer
        '''
        self._mgr.floating_widgets.append(floating_widget)
        logger.debug('floating widgets count = %d',
                     len(self._mgr.floating_widgets))

    def remove_floating_widget(self, floating_widget: FloatingDockContainer):
        '''
        Remove the given floating widget from the list of registered floating widgets

        Parameters
        ----------
        floating_widget : FloatingDockContainer
        '''
        if floating_widget not in self._mgr.floating_widgets:
            logger.error('qtpydocking bug; floating widget not in list: '
                         '%s not in %s', floating_widget,
                         self._mgr.floating_widgets)
            return

        self._mgr.floating_widgets.remove(floating_widget)

    def register_dock_container(self, dock_container: DockContainerWidget):
        '''
        Registers the given dock container widget

        Parameters
        ----------
        dock_container : DockContainerWidget
        '''
        self._mgr.containers.append(dock_container)

    def remove_dock_container(self, dock_container: DockContainerWidget):
        '''
        Remove dock container from the internal list of registered dock containers

        Parameters
        ----------
        dock_container : DockContainerWidget
        '''
        if self is not dock_container and dock_container in self._mgr.containers:
            self._mgr.containers.remove(dock_container)

    def container_overlay(self) -> DockOverlay:
        '''
        Overlay for containers

        Returns
        -------
        value : DockOverlay
        '''
        return self._mgr.container_overlay

    def dock_area_overlay(self) -> DockOverlay:
        '''
        Overlay for dock areas

        Returns
        -------
        value : DockOverlay
        '''
        return self._mgr.dock_area_overlay

    # TODO: property
    def config_flags(self) -> DockFlags:
        '''
        This function returns the global configuration flags

        Returns
        -------
        value : DockFlags
        '''
        return self._mgr.config_flags

    def set_config_flags(self, flags: DockFlags):
        '''
        Sets the global configuration flags for the whole docking system. Call
        this function before you create your first dock widget.

        Parameters
        ----------
        flags : DockFlags
        '''
        self._mgr.config_flags = flags

    def add_dock_widget(
            self, area: DockWidgetArea,
            dock_widget: 'DockWidget',
            dock_area_widget: 'DockAreaWidget' = None
    ) -> 'DockAreaWidget':
        '''
        Adds dock_widget into the given area. If DockAreaWidget is not null,
        then the area parameter indicates the area into the DockAreaWidget. If
        DockAreaWidget is null, the Dockwidget will be dropped into the
        container. If you would like to add a dock widget tabified, then you
        need to add it to an existing dock area object into the
        CenterDockWidgetArea. The following code shows this:

        Parameters
        ----------
        area : DockWidgetArea
        dock_widget : DockWidget
        dock_area_widget : DockAreaWidget, optional

        Returns
        -------
        value : DockAreaWidget
        '''
        self._mgr.dock_widgets_map[dock_widget.objectName()] = dock_widget
        return super().add_dock_widget(area, dock_widget, dock_area_widget)

    def add_dock_widget_tab(self, area: DockWidgetArea,
                            dockwidget: 'DockWidget') -> 'DockAreaWidget':
        '''
        This function will add the given Dockwidget to the given dock area as a
        new tab. If no dock area widget exists for the given area identifier, a
        new dock area widget is created.

        Parameters
        ----------
        area : DockWidgetArea
        dockwidget : DockWidget

        Returns
        -------
        value : DockAreaWidget
        '''
        area_widget = self.last_added_dock_area_widget(area)
        if area_widget is not None:
            return self.add_dock_widget(DockWidgetArea.center,
                                        dockwidget, area_widget)

        opened_areas = self.opened_dock_areas()
        return self.add_dock_widget(area, dockwidget,
                                    opened_areas[-1] if opened_areas else None)

    def add_dock_widget_tab_to_area(self, dockwidget: 'DockWidget',
                                    dock_area_widget: 'DockAreaWidget'
                                    ) -> 'DockAreaWidget':
        '''
        This function will add the given Dockwidget to the given DockAreaWidget
        as a new tab.

        Parameters
        ----------
        dockwidget : DockWidget
        dock_area_widget : DockAreaWidget

        Returns
        -------
        value : DockAreaWidget
        '''
        return self.add_dock_widget(DockWidgetArea.center,
                                    dockwidget, dock_area_widget)

    def find_dock_widget(self, object_name: str) -> 'DockWidget':
        '''
        Searches for a registered doc widget with the given ObjectName

        Parameters
        ----------
        object_name : str

        Returns
        -------
        value : DockWidget
        '''
        return self._mgr.dock_widgets_map.get(object_name, None)

    def dock_widgets_map(self) -> dict:
        '''
        This function returns a readable reference to the internal dock widgets
        map so that it is possible to iterate over all dock widgets

        Returns
        -------
        value : dict:
        '''
        return dict(self._mgr.dock_widgets_map)

    def remove_dock_widget(self, widget: 'DockWidget'):
        '''
        Removes a given DockWidget

        Parameters
        ----------
        widget : DockWidget
        '''
        self._mgr.dock_widgets_map.pop(widget.objectName())
        super().remove_dock_widget(widget)

    def dock_containers(self) -> list:
        '''
        Returns the list of all active and visible dock containers

        Dock containers are the main dock manager and all floating widgets.

        Returns
        -------
        value : list
        '''
        # qtpydocking TODO containers getting deleted
        for container in list(self._mgr.containers):
            try:
                container.isVisible()
            except RuntimeError as ex:
                self._mgr.containers.remove(container)
                logger.debug('qtpydocking TODO, container deleted',
                             exc_info=ex)

        return list(self._mgr.containers)

    def floating_widgets(self) -> list:
        '''
        Returns the list of all floating widgets

        Returns
        -------
        value : list
        '''
        return self._mgr.floating_widgets

    def z_order_index(self) -> int:
        '''
        This function always return 0 because the main window is always behind
        any floating widget

        Returns
        -------
        value : unsigned int
        '''
        return 0

    def save_state(self, version: int = 0) -> QByteArray:
        '''
        Saves the current state of the dockmanger and all its dock widgets into
        the returned QByteArray.

        See also `config_flags`, which allow for auto-formatting and compression
        of the resulting XML file.

        Parameters
        ----------
        version : int

        Returns
        -------
        value : QByteArray
        '''
        xmldata = QByteArray()
        stream = QXmlStreamWriter(xmldata)
        stream.setAutoFormatting(
            DockFlags.xml_auto_formatting in self._mgr.config_flags)
        stream.writeStartDocument()
        stream.writeStartElement("QtAdvancedDockingSystem")
        stream.writeAttribute("Version", str(version))
        stream.writeAttribute("Containers", str(len(self._mgr.containers)))
        for container in self._mgr.containers:
            if isinstance(container, DockManager):
                DockContainerWidget.save_state(container, stream)
            else:
                container.save_state(stream)

        stream.writeEndElement()
        stream.writeEndDocument()

        return (qCompress(xmldata, 9)
                if DockFlags.xml_compression in self._mgr.config_flags
                and qCompress is not None
                else xmldata)

    def restore_state(self, state: QByteArray, version: int = 0) -> bool:
        '''
        Restores the state of this dockmanagers dockwidgets. The version number
        is compared with that stored in state. If they do not match, the
        dockmanager's state is left unchanged, and this function returns false;
        otherwise, the state is restored, and this function returns true.

        Parameters
        ----------
        state : QByteArray
        version : int

        Returns
        -------
        value : bool
        '''
        if not state.startsWith(b'<?xml'):
            if qUncompress is None:
                raise RuntimeError(
                        'Compression utilities unavailable with the '
                        'current qt bindings')
            state = qUncompress(state)

        # Prevent multiple calls as long as state is not restore. This may
        # happen, if QApplication.processEvents() is called somewhere
        if self._mgr.restoring_state:
            return False

        # We hide the complete dock manager here. Restoring the state means
        # that DockWidgets are removed from the DockArea internal stack layout
        # which in turn  means, that each time a widget is removed the stack
        # will show and raise the next available widget which in turn
        # triggers show events for the dock widgets. To avoid this we hide the
        # dock manager. Because there will be no processing of application
        # events until this function is finished, the user will not see this
        # hiding
        is_hidden = self.isHidden()
        if not is_hidden:
            self.hide()

        try:
            self._mgr.restoring_state = True
            self.restoring_state.emit()
            result = self._mgr.restore_state(state, version)
        finally:
            self._mgr.restoring_state = False

        self.state_restored.emit()
        if not is_hidden:
            self.show()

        return result

    def add_perspective(self, unique_perspective_name: str):
        '''
        Saves the current perspective to the internal list of perspectives. A
        perspective is the current state of the dock manager assigned with a
        certain name. This makes it possible for the user, to switch between
        different perspectives quickly. If a perspective with the given name
        already exists, then it will be overwritten with the new state.

        Parameters
        ----------
        unique_perspective_name : str
        '''
        self._mgr.perspectives[unique_perspective_name] = self.save_state()
        self.perspective_list_changed.emit()

    def remove_perspectives(self, *names):
        '''
        Removes the given perspective(s) from the dock manager

        Parameters
        ----------
        *names : str
        '''
        count = 0
        for name in names:
            try:
                del self._mgr.perspectives[name]
            except KeyError:
                ...
            else:
                count += 1

        if count:
            self.perspectives_removed.emit()
            self.perspective_list_changed.emit()

    def perspective_names(self) -> List[str]:
        '''
        Returns the names of all available perspectives

        Returns
        -------
        value : list
        '''
        return list(self._mgr.perspectives.keys())

    def save_perspectives(self, settings: QSettings):
        '''
        Saves the perspectives to the given settings file.

        Parameters
        ----------
        settings : QSettings
        '''
        settings.beginWriteArray("Perspectives", len(self._mgr.perspectives))

        for i, (key, perspective) in enumerate(self._mgr.perspectives.items()):
            settings.setArrayIndex(i)
            settings.setValue("Name", key)
            settings.setValue("State", perspective)

        settings.endArray()

    def load_perspectives(self, settings: QSettings):
        '''
        Loads the perspectives from the given settings file

        Parameters
        ----------
        settings : QSettings
        '''
        self._mgr.perspectives.clear()
        size = settings.beginReadArray("Perspectives")
        if not size:
            settings.endArray()
            return

        for i in range(size):
            settings.setArrayIndex(i)
            name = settings.value("Name")
            data = settings.value("State")
            if not name or not data:
                continue

            self._mgr.perspectives[name] = data

        settings.endArray()

    def add_toggle_view_action_to_menu(self, toggle_view_action: QAction,
                                       group: str, group_icon: QIcon) -> QAction:
        '''
        Adds a toggle view action to the the internal view menu. You can either
        manage the insertion of the toggle view actions in your application or
        you can add the actions to the internal view menu and then simply
        insert the menu object into your.

        Parameters
        ----------
        toggle_view_action : QAction
        group : str
        group_icon : QIcon

        Returns
        -------
        value : QAction
        '''
        order = self._mgr.menu_insertion_order
        alphabetically_sorted = (
            InsertionOrder.by_spelling == order
        )

        if not group:
            self._mgr.add_action_to_menu(toggle_view_action,
                                         self._mgr.view_menu,
                                         alphabetically_sorted)
            return toggle_view_action

        try:
            group_menu = self._mgr.view_menu_groups[group]
        except KeyError:
            group_menu = QMenu(group, self)
            group_menu.setIcon(group_icon)
            self._mgr.add_action_to_menu(
                group_menu.menuAction(), self._mgr.view_menu,
                alphabetically_sorted)
            self._mgr.view_menu_groups[group] = group_menu

        self._mgr.add_action_to_menu(toggle_view_action, group_menu,
                                     alphabetically_sorted)
        return group_menu.menuAction()

    def view_menu(self) -> QMenu:
        '''
        This function returns the internal view menu. To fill the view menu,
        you can use the addToggleViewActionToMenu() function.

        Returns
        -------
        value : QMenu
        '''
        return self._mgr.view_menu

    def set_view_menu_insertion_order(self, order: InsertionOrder):
        '''
        Define the insertion order for toggle view menu items. The order
        defines how the actions are added to the view menu. The default
        insertion order is MenuAlphabeticallySorted to make it easier for users
        to find the menu entry for a certain dock widget. You need to call this
        function befor you insert the first menu item into the view menu.

        Parameters
        ----------
        order : InsertionOrder
        '''
        self._mgr.menu_insertion_order = order

    def is_restoring_state(self) -> bool:
        '''
        This function returns true between the restoringState() and
        stateRestored() signals.

        Returns
        -------
        value : bool
        '''
        return self._mgr.restoring_state

    def open_perspective(self, perspective_name: str):
        '''
        Opens the perspective with the given name.

        Parameters
        ----------
        perspective_name : str
        '''
        try:
            perspective = self._mgr.perspectives[perspective_name]
        except KeyError:
            return

        self.opening_perspective.emit(perspective_name)
        self.restore_state(perspective)
        self.perspective_opened.emit(perspective_name)

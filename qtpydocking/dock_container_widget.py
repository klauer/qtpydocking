import logging
from typing import TYPE_CHECKING, List, Dict, Tuple, Optional

from qtpy.QtCore import (QByteArray, QEvent, QPoint, QXmlStreamReader,
                         QXmlStreamWriter, Qt, Signal)
from qtpy.QtWidgets import QFrame, QGridLayout, QSplitter, QWidget

from .util import (find_parent, hide_empty_parent_splitters,
                   emit_top_level_event_for_widget, find_child, find_children)
from .enums import (DockWidgetArea, DockWidgetFeature, TitleBarButton,
                    DockFlags, DockInsertParam)
from .dock_splitter import DockSplitter
from .dock_area_widget import DockAreaWidget


if TYPE_CHECKING:
    from . import DockManager, DockWidget, FloatingDockContainer


logger = logging.getLogger(__name__)

# TODO global?
_z_order_counter = 0

def dock_area_insert_parameters(area: DockWidgetArea) -> DockInsertParam:
    '''
    Returns the insertion parameters for the given dock area

    Parameters
    ----------
    area : DockWidgetArea

    Returns
    -------
    value : DockInsertParam
    '''
    if area == DockWidgetArea.top:
        return DockInsertParam(Qt.Vertical, False)
    if area == DockWidgetArea.right:
        return DockInsertParam(Qt.Horizontal, True)
    if area in (DockWidgetArea.center,
                DockWidgetArea.bottom):
        return DockInsertParam(Qt.Vertical, True)
    if area == DockWidgetArea.left:
        return DockInsertParam(Qt.Horizontal, False)

    return DockInsertParam(Qt.Vertical, False)


def insert_widget_into_splitter(splitter: QSplitter, widget: QWidget,
                                append: bool):
    '''
    Helper function to ease insertion of dock area into splitter

    Parameters
    ----------
    splitter : QSplitter
    widget : QWidget
    append : bool
    '''
    if append:
        return splitter.addWidget(widget)
    return splitter.insertWidget(0, widget)


def replace_splitter_widget(splitter: QSplitter, from_: QWidget, to: QWidget):
    '''
    Replace the from widget in the given splitter with the To widget

    Parameters
    ----------
    splitter : QSplitter
    from : QWidget
    to : QWidget
    '''
    index = splitter.indexOf(from_)
    from_.setParent(None)
    logger.debug('replace splitter widget %d %s -> %s', index, from_, to)
    splitter.insertWidget(index, to)


class DockContainerWidgetPrivate:
    public: 'DockContainerWidget'
    dock_manager: 'DockManager'
    z_order_index: int
    dock_areas: List[DockAreaWidget]
    layout: QGridLayout
    root_splitter: DockSplitter
    is_floating: bool
    last_added_area_cache: Dict[DockWidgetArea, DockAreaWidget]
    _visible_dock_area_count: int
    top_level_dock_area: DockAreaWidget

    def __init__(self, public):
        '''
        Private data constructor

        Parameters
        ----------
        public : DockContainerWidget
        '''
        self.public = public
        self.dock_manager = None
        self.z_order_index = 0
        self.dock_areas = []
        self.layout = None
        self.root_splitter = None
        self.is_floating = False
        self.last_added_area_cache = {}
        self._visible_dock_area_count = -1
        self.top_level_dock_area = None

    def dock_widget_into_container(self, area: DockWidgetArea,
                                   dockwidget: 'DockWidget') -> DockAreaWidget:
        '''
        Adds dock widget to container and returns the dock area that contains
        the inserted dock widget

        Parameters
        ----------
        area : DockWidgetArea
        dockwidget : DockWidget

        Returns
        -------
        value : DockAreaWidget
        '''
        new_dock_area = DockAreaWidget(self.dock_manager, self.public)
        new_dock_area.add_dock_widget(dockwidget)
        self.add_dock_area(new_dock_area, area)
        new_dock_area.update_title_bar_visibility()
        self.last_added_area_cache[area] = new_dock_area
        return new_dock_area

    def dock_widget_into_dock_area(self, area: DockWidgetArea,
                                   dock_widget: 'DockWidget',
                                   target_dock_area: DockAreaWidget) -> DockAreaWidget:
        '''
        Adds dock widget to a existing DockWidgetArea

        Parameters
        ----------
        area : DockWidgetArea
        dockwidget : DockWidget
        target_dock_area : DockAreaWidget

        Returns
        -------
        value : DockAreaWidget
        '''
        if area == DockWidgetArea.center:
            target_dock_area.add_dock_widget(dock_widget)
            return target_dock_area

        new_dock_area = DockAreaWidget(self.dock_manager, self.public)
        new_dock_area.add_dock_widget(dock_widget)

        insert_param = dock_area_insert_parameters(area)
        target_area_splitter = find_parent(QSplitter, target_dock_area)
        index = target_area_splitter.indexOf(target_dock_area)
        if target_area_splitter.orientation() == insert_param.orientation:
            logger.debug('TargetAreaSplitter.orientation() == insert_orientation')
            target_area_splitter.insertWidget(index + insert_param.insert_offset, new_dock_area)
        else:
            logger.debug('TargetAreaSplitter.orientation() != insert_orientation')
            new_splitter = self.new_splitter(insert_param.orientation)
            new_splitter.addWidget(target_dock_area)
            insert_widget_into_splitter(new_splitter, new_dock_area,
                                        insert_param.append)
            target_area_splitter.insertWidget(index, new_splitter)

        self.append_dock_areas(new_dock_area)
        self.emit_dock_areas_added()
        return new_dock_area

    def add_dock_area(self, new_dock_area: DockAreaWidget, area: DockWidgetArea):
        '''
        Add dock area to this container

        Parameters
        ----------
        new_dock_widget : DockAreaWidget
        area : DockWidgetArea
        '''
        insert_param = dock_area_insert_parameters(area)

        # As long as we have only one dock area in the splitter we can adjust
        # its orientation
        if len(self.dock_areas) <= 1:
            self.root_splitter.setOrientation(insert_param.orientation)

        splitter = self.root_splitter
        if splitter.orientation() == insert_param.orientation:
            insert_widget_into_splitter(splitter, new_dock_area, insert_param.append)
        else:
            new_splitter = self.new_splitter(insert_param.orientation)
            if insert_param.append:
                self.layout.replaceWidget(splitter, new_splitter)
                new_splitter.addWidget(splitter)
                new_splitter.addWidget(new_dock_area)
            else:
                new_splitter.addWidget(new_dock_area)
                self.layout.replaceWidget(splitter, new_splitter)
                new_splitter.addWidget(splitter)

            self.root_splitter = new_splitter

        self.append_dock_areas(new_dock_area)
        new_dock_area.update_title_bar_visibility()
        self.emit_dock_areas_added()

        # TODO not in ads - qtpydocking bug?
        new_dock_area.destroyed.connect(self.public.remove_dock_area)

    def drop_into_container(self,
                            floating_widget: 'FloatingDockContainer',
                            area: DockWidgetArea):
        '''
        Drop floating widget into container

        Parameters
        ----------
        floating_widget : FloatingDockContainer
        area : DockWidgetArea
        '''
        insert_param = dock_area_insert_parameters(area)
        floating_dock_container = floating_widget.dock_container()

        new_dock_areas = find_children(
            floating_dock_container, DockAreaWidget, '', Qt.FindChildrenRecursively)

        single_dropped_dock_widget = floating_dock_container.top_level_dock_widget()
        single_dock_widget = self.public.top_level_dock_widget()
        splitter = self.root_splitter
        if len(self.dock_areas) <= 1:
            splitter.setOrientation(insert_param.orientation)
        elif splitter.orientation() != insert_param.orientation:
            new_splitter = self.new_splitter(insert_param.orientation)
            self.layout.replaceWidget(splitter, new_splitter)
            new_splitter.addWidget(splitter)
            splitter = new_splitter

        # Now we can insert the floating widget content into this container
        floating_splitter = floating_dock_container.root_splitter()
        if floating_splitter.count() == 1:
            insert_widget_into_splitter(splitter, floating_splitter.widget(0),
                                        insert_param.append)
        elif floating_splitter.orientation() == insert_param.orientation:
            while floating_splitter.count():
                insert_widget_into_splitter(splitter,
                                            floating_splitter.widget(0),
                                            insert_param.append)
        else:
            insert_widget_into_splitter(splitter, floating_splitter,
                                        insert_param.append)

        self.root_splitter = splitter
        self.add_dock_areas_to_list(new_dock_areas)
        floating_widget.deleteLater()

        emit_top_level_event_for_widget(single_dropped_dock_widget, False)
        emit_top_level_event_for_widget(single_dock_widget, False)

        # If we dropped the floating widget into the main dock container that does
        # not contain any dock widgets, then splitter is invisible and we need to
        # show it to display the docked widgets
        if not splitter.isVisible():
            splitter.show()

        self.public.dump_layout()

    def drop_into_section(self, floating_widget: 'FloatingDockContainer',
                          target_area: DockAreaWidget, area: DockWidgetArea):
        '''
        Drop floating widget into dock area

        Parameters
        ----------
        floating_widget : FloatingDockContainer
        target_area : DockAreaWidget
        area : DockWidgetArea
        '''
        # Dropping into center means all dock widgets in the dropped floating
        # widget will become tabs of the drop area
        if area == DockWidgetArea.center:
            self.drop_into_center_of_section(floating_widget, target_area)
            return

        insert_param = dock_area_insert_parameters(area)

        # noinspection PyArgumentList
        new_dock_areas = find_children(
            floating_widget.dock_container(), DockAreaWidget, '', Qt.FindChildrenRecursively)

        target_area_splitter = find_parent(QSplitter, target_area)

        if not target_area_splitter:
            splitter = self.new_splitter(insert_param.orientation)
            self.layout.replaceWidget(target_area, splitter)
            splitter.addWidget(target_area)
            target_area_splitter = splitter

        area_index = target_area_splitter.indexOf(target_area)

        floating_splitter = find_child(
            floating_widget.dock_container(), QWidget, '', Qt.FindDirectChildrenOnly)

        if target_area_splitter.orientation() == insert_param.orientation:
            sizes = target_area_splitter.sizes()
            target_area_size = (target_area.width()
                                if insert_param.orientation == Qt.Horizontal
                                else target_area.height()
                                )
            adjust_splitter_sizes = True
            if (floating_splitter.orientation() != insert_param.orientation
                    and floating_splitter.count() > 1):
                target_area_splitter.insertWidget(
                    area_index + insert_param.insert_offset,
                    floating_splitter)
            else:
                adjust_splitter_sizes = (floating_splitter.count() == 1)
                insert_index = area_index + insert_param.insert_offset
                while floating_splitter.count():
                    insert_index += 1
                    target_area_splitter.insertWidget(insert_index,
                                                      floating_splitter.widget(0))


            if adjust_splitter_sizes:
                size = (target_area_size-target_area_splitter.handleWidth()) / 2
                sizes[area_index] = size
                sizes.insert(area_index, size)
                target_area_splitter.setSizes(sizes)

        else:
            new_splitter = self.new_splitter(insert_param.orientation)
            target_area_size = (target_area.width()
                                if insert_param.orientation == Qt.Horizontal
                                else target_area.height()
                                )
            adjust_splitter_sizes = True
            if (floating_splitter.orientation() != insert_param.orientation) and floating_splitter.count() > 1:
                new_splitter.addWidget(floating_splitter)
            else:
                adjust_splitter_sizes = (floating_splitter.count() == 1)
                while floating_splitter.count():
                    new_splitter.addWidget(floating_splitter.widget(0))

            # Save the sizes before insertion and restore it later to prevent
            # shrinking of existing area
            sizes = target_area_splitter.sizes()
            insert_widget_into_splitter(new_splitter, target_area, not insert_param.append)
            if adjust_splitter_sizes:
                size = target_area_size/2
                new_splitter.setSizes((size, size))

            target_area_splitter.insertWidget(area_index, new_splitter)
            target_area_splitter.setSizes(sizes)

        logger.debug('Deleting floating_widget %s', floating_widget)
        floating_widget.deleteLater()
        self.add_dock_areas_to_list(new_dock_areas)
        self.public.dump_layout()

    def drop_into_center_of_section(self, floating_widget: 'FloatingDockContainer',
                                    target_area: DockAreaWidget):
        '''
        Creates a new tab for a widget dropped into the center of a section

        Parameters
        ----------
        floating_widget : FloatingDockContainer
        target_area : DockAreaWidget
        '''
        floating_container = floating_widget.dock_container()
        new_dock_widgets = floating_container.dock_widgets()
        top_level_dock_area = floating_container.top_level_dock_area()
        new_current_index = -1

        # If the floating widget contains only one single dock are, then the
        # current dock widget of the dock area will also be the future current
        # dock widget in the drop area.
        if top_level_dock_area is not None:
            new_current_index = top_level_dock_area.current_index()

        for i, dock_widget in enumerate(new_dock_widgets):
            target_area.insert_dock_widget(i, dock_widget, False)

            # If the floating widget contains multiple visible dock areas, then we
            # simply pick the first visible open dock widget and make it
            # the current one.
            if new_current_index < 0 and not dock_widget.is_closed():
                new_current_index = i

        target_area.set_current_index(new_current_index)
        floating_widget.deleteLater()
        target_area.update_title_bar_visibility()

    def add_dock_areas_to_list(self, new_dock_areas: list):
        '''
        Adds new dock areas to the internal dock area list

        Parameters
        ----------
        new_dock_areas : list
        '''
        count_before = len(self.dock_areas)
        new_area_count = len(new_dock_areas)
        self.append_dock_areas(*new_dock_areas)

        # If the user dropped a floating widget that contains only one single
        # visible dock area, then its title bar button TitleBarButtonUndock is
        # likely hidden. We need to ensure, that it is visible
        for dock_area in new_dock_areas:
            undock = dock_area.title_bar_button(TitleBarButton.undock)
            undock.setVisible(True)
            close = dock_area.title_bar_button(TitleBarButton.close)
            close.setVisible(True)

        # We need to ensure, that the dock area title bar is visible. The title bar
        # is invisible, if the dock are is a single dock area in a floating widget.
        if count_before == 1:
            self.dock_areas[0].update_title_bar_visibility()
        if new_area_count == 1:
            self.dock_areas[-1].update_title_bar_visibility()

        self.emit_dock_areas_added()

    def append_dock_areas(self, *new_dock_areas):
        '''
        Wrapper function for DockAreas append, that ensures that dock area
        signals are properly connected to dock container slots

        Parameters
        ----------
        *new_dock_areas : DockAreaWidget
        '''
        self.dock_areas.extend(new_dock_areas)
        for dock_area in new_dock_areas:
            dock_area.view_toggled.connect(self.on_dock_area_view_toggled)

    def save_child_nodes_state(self, stream: QXmlStreamWriter, widget: QWidget):
        '''
        Save state of child nodes

        Parameters
        ----------
        stream : QXmlStreamWriter
        widget : QWidget
        '''
        if isinstance(widget, QSplitter):
            splitter = widget
            stream.writeStartElement("Splitter")
            orientation = ('-' if splitter.orientation() == Qt.Horizontal
                           else "|")
            stream.writeAttribute("Orientation", orientation)
            stream.writeAttribute("Count", str(splitter.count()))
            logger.debug('NodeSplitter orient: %s WidgetCount: %s',
                         orientation, splitter.count())

            for i in range(splitter.count()):
                self.save_child_nodes_state(stream, splitter.widget(i))

            stream.writeStartElement("Sizes")
            for Size in splitter.sizes():
                stream.writeCharacters(str(Size)+" ")

            stream.writeEndElement()
            stream.writeEndElement()
        elif isinstance(widget, DockAreaWidget):
            widget.save_state(stream)

    def restore_child_nodes(self, stream: QXmlStreamReader,
                            testing: bool) -> Tuple[bool, Optional[QWidget]]:
        '''
        Restore state of child nodes.

        Parameters
        ----------
        stream : QXmlStreamReader
        created_widget : QWidget
        testing : bool

        Returns
        -------
        value : bool
        widget : QWidget
        '''
        result = True
        widget = None
        while stream.readNextStartElement():
            if stream.name() == "Splitter":
                result, widget = self.restore_splitter(stream, testing)
            elif stream.name() == "Area":
                result, widget = self.restore_dock_area(stream, testing)
            else:
                stream.skipCurrentElement()
            logger.debug('restored child node %s: %s', stream.name(), widget)

        return result, widget

    def restore_splitter(self, stream: QXmlStreamReader, testing: bool
                         ) -> Tuple[bool, Optional[QWidget]]:
        '''
        Restores a splitter.

        Parameters
        ----------
        stream : QXmlStreamReader
        created_widget : QWidget
        testing : bool

        Returns
        -------
        value : bool
        widget : QWidget
        '''
        orientation_str = stream.attributes().value("Orientation")
        if orientation_str.startswith("-"):
            orientation = Qt.Horizontal
        elif orientation_str.startswith("|"):
            orientation = Qt.Vertical
        else:
            return False, None

        widget_count = int(stream.attributes().value("Count"))
        if not widget_count:
            return False, None

        logger.debug('Restore NodeSplitter Orientation: %s  WidgetCount: %s',
                     orientation, widget_count)

        splitter = (None if testing
                    else self.new_splitter(orientation))
        visible = False
        sizes = []

        while stream.readNextStartElement():
            child_node = None
            if stream.name() == "Splitter":
                result, child_node = self.restore_splitter(stream, testing)
                if not result:
                    return False, None
            elif stream.name() == "Area":
                result, child_node = self.restore_dock_area(stream, testing)
                if not result:
                    return False, None
            elif stream.name() == "Sizes":
                s_sizes = stream.readElementText().strip()
                sizes = [int(sz) for sz in s_sizes.split(' ')]
                logger.debug('Sizes: %s (from s_sizes: %s)', sizes, s_sizes)
            else:
                stream.skipCurrentElement()

            if splitter is not None and child_node is not None:
                logger.debug('ChildNode isVisible %s isVisibleTo %s',
                             child_node.isVisible(),
                             child_node.isVisibleTo(splitter))
                splitter.addWidget(child_node)
                visible |= child_node.isVisibleTo(splitter)

        if len(sizes) != widget_count:
            return False, None

        if testing:
            splitter = None
        else:
            if not splitter.count():
                splitter.deleteLater()
                splitter = None
            else:
                splitter.setSizes(sizes)
                splitter.setVisible(visible)

        return True, splitter

    def restore_dock_area(self, stream: QXmlStreamReader, testing: bool) -> Tuple[bool, QWidget]:
        '''
        Restores a dock area.

        Parameters
        ----------
        stream : QXmlStreamReader
        created_widget : QWidget
        testing : bool

        Returns
        -------
        value : bool
        widget : QWidget
        '''
        tabs = int(stream.attributes().value("Tabs"))
        current_dock_widget = stream.attributes().value("Current")
        logger.debug('Restore NodeDockArea Tabs: %s current: %s',
                     tabs, current_dock_widget)
        dock_area = None
        if not testing:
            dock_area = DockAreaWidget(self.dock_manager, self.public)

        while stream.readNextStartElement():
            if stream.name() != "Widget":
                continue

            object_name = stream.attributes().value("Name")
            if not object_name:
                return False, None

            closed = bool(int(stream.attributes().value("Closed")))

            stream.skipCurrentElement()
            dock_widget = self.dock_manager.find_dock_widget(object_name)
            if dock_widget and dock_area:
                logger.debug('Dock Widget found - parent %s', dock_widget.parent())
                # We hide the DockArea here to prevent the short display (the flashing)
                # of the dock areas during application startup
                dock_area.hide()
                dock_area.add_dock_widget(dock_widget)
                dock_widget.set_toggle_view_action_checked(not closed)
                dock_widget.set_closed_state(closed)
                dock_widget.setProperty("closed", closed)
                dock_widget.setProperty("dirty", False)

        if testing:
            return True, None

        if not dock_area.dock_widgets_count():
            dock_area.deleteLater()
            dock_area = None
        else:
            dock_area.setProperty("currentDockWidget", current_dock_widget)
            self.append_dock_areas(dock_area)

        return True, dock_area

    def dump_recursive(self, level: int, widget: QWidget):
        '''
        Helper function for recursive dumping of layout

        Parameters
        ----------
        level : int
        widget : QWidget
        '''
        indent = ' ' * level*4
        if isinstance(widget, QSplitter):
            splitter = widget
            logger.debug(
                "%sSplitter %s v: %s c: %s",
                indent,
                ('|' if splitter.orientation() == Qt.Vertical else '--'),
                (' ' if splitter.isHidden() else 'v'),
                splitter.count()
            )

            for i in range(splitter.count()):
                self.dump_recursive(level + 1, splitter.widget(i))
        elif isinstance(widget, DockAreaWidget):
            dock_area = widget
            logger.debug('%sDockArea', indent)
            logger.debug('%s%s %s DockArea',
                         indent,
                         ' ' if dock_area.isHidden() else 'v',
                         ' ' if dock_area.open_dock_widgets_count() > 0 else 'c',
                         )

            indent = ' ' * (level + 1) * 4
            for i, dock_widget in enumerate(dock_area.dock_widgets()):
                logger.debug('%s%s%s%s %s', indent,
                             '*' if i == dock_area.current_index() else ' ',
                             ' ' if i == dock_widget.isHidden() else 'v',
                             'c' if i == dock_widget.is_closed() else ' ',
                             dock_widget.windowTitle()
                             )

    def visible_dock_area_count(self) -> int:
        '''
        Access function for the visible dock area counter

        Returns
        -------
        value : int
        '''
        # Lazy initialisation - we initialize the VisibleDockAreaCount variable
        # on first use
        if self._visible_dock_area_count > -1:
            return self._visible_dock_area_count

        self._visible_dock_area_count = 0
        for dock_area in self.dock_areas:
            if not dock_area.isHidden():
                self._visible_dock_area_count += 1
        return self._visible_dock_area_count

    def on_visible_dock_area_count_changed(self):
        '''
        The visible dock area count changes, if dock areas are remove, added or when its view is toggled
        '''
        top_level_dock_area = self.public.top_level_dock_area()
        if top_level_dock_area is not None:
            self.top_level_dock_area = self.top_level_dock_area
            top_level_dock_area.title_bar_button(
                TitleBarButton.undock).setVisible(False or not self.public.is_floating())
            top_level_dock_area.title_bar_button(
                TitleBarButton.close).setVisible(False or not self.public.is_floating())

        elif self.top_level_dock_area:
            self.top_level_dock_area.title_bar_button(
                TitleBarButton.undock).setVisible(True)
            self.top_level_dock_area.title_bar_button(
                TitleBarButton.close).setVisible(True)
            self.top_level_dock_area = None

    def emit_dock_areas_removed(self):
        self.on_visible_dock_area_count_changed()
        self.public.dock_areas_removed.emit()

    def emit_dock_areas_added(self):
        self.on_visible_dock_area_count_changed()
        self.public.dock_areas_added.emit()

    def new_splitter(self, orientation: Qt.Orientation, parent: QWidget = None) -> DockSplitter:
        '''
        Helper function for creation of new splitter

        Parameters
        ----------
        orientation : Qt.Orientation
        parent : QWidget, optional

        Returns
        -------
        value : DockSplitter
        '''
        splitter = DockSplitter(orientation, parent)
        opaque_resize = (DockFlags.opaque_splitter_resize in
                         self.dock_manager.config_flags())
        splitter.setOpaqueResize(opaque_resize)
        splitter.setChildrenCollapsible(False)
        return splitter

    def on_dock_area_view_toggled(self, visible: bool):
        '''
        On dock area view toggled

        Parameters
        ----------
        visible : bool
        '''
        try:
            dock_area = self.public.sender()
        except RuntimeError:
            logger.exception('qtpydocking bug')
            return

        self.visible_dock_area_count()
        if visible:
            self._visible_dock_area_count += 1
        else:
            self._visible_dock_area_count -= 1

        self.on_visible_dock_area_count_changed()
        self.public.dock_area_view_toggled.emit(dock_area, visible)


class DockContainerWidget(QFrame):
    # This signal is emitted if one or multiple dock areas has been added to
    # the internal list of dock areas. If multiple dock areas are inserted,
    # this signal is emitted only once
    dock_areas_added = Signal()

    # This signal is emitted if one or multiple dock areas has been removed
    dock_areas_removed = Signal()

    # This signal is emitted if a dock area is opened or closed via
    # toggleView() function
    dock_area_view_toggled = Signal(DockAreaWidget, bool)

    def __init__(self, dock_manager: 'DockManager', parent: QWidget):
        '''

        Parameters
        ----------
        dock_manager : DockManager
        parent : QWidget
        '''
        super().__init__(parent)
        self.d = DockContainerWidgetPrivate(self)
        self.d.dock_manager = dock_manager
        self.d.is_floating = self.floating_widget() is not None
        self.d.layout = QGridLayout()
        self.d.layout.setContentsMargins(0, 1, 0, 1)
        self.d.layout.setSpacing(0)
        self.setLayout(self.d.layout)

        # The function d.new_splitter() accesses the config flags from dock
        # manager which in turn requires a properly constructed dock manager.
        # If this dock container is the dock manager, then it is not properly
        # constructed yet because this base class constructor is called before
        # the constructor of the DockManager private class
        if dock_manager is not self:
            self.d.dock_manager.register_dock_container(self)
            self.create_root_splitter()

    def __repr__(self):
        return f'<{self.__class__.__name__} is_floating={self.d.is_floating}>'

    def deleteLater(self):
        if self.d.dock_manager:
            self.d.dock_manager.remove_dock_container(self)

        super().deleteLater()

    def event(self, e: QEvent) -> bool:
        '''
        Handles activation events to update zOrderIndex

        Parameters
        ----------
        e : QEvent

        Returns
        -------
        value : bool
        '''
        result = super().event(e)
        global _z_order_counter  # TODO
        if e.type() == QEvent.WindowActivate:
            _z_order_counter += 1
            self.d.z_order_index = _z_order_counter
        elif e.type() == QEvent.Show and not self.d.z_order_index:
            _z_order_counter += 1
            self.d.z_order_index = _z_order_counter

        return result

    def root_splitter(self) -> QSplitter:
        '''
        Access function for the internal root splitter

        Returns
        -------
        value : QSplitter
        '''
        return self.d.root_splitter

    def create_root_splitter(self):
        '''
        Helper function for creation of the root splitter
        '''
        if self.d.root_splitter:
            return

        self.d.root_splitter = self.d.new_splitter(Qt.Horizontal)
        self.d.layout.addWidget(self.d.root_splitter)

    def drop_floating_widget(self,
                             floating_widget: 'FloatingDockContainer',
                             target_pos: QPoint):
        '''
        Drop floating widget into the container

        Parameters
        ----------
        floating_widget : FloatingDockContainer
        target_pos : QPoint
        '''
        logger.debug('DockContainerWidget.dropFloatingWidget')
        dock_area = self.dock_area_at(target_pos)
        drop_area = DockWidgetArea.invalid
        container_drop_area = self.d.dock_manager.container_overlay().drop_area_under_cursor()
        floating_top_level_dock_widget = floating_widget.top_level_dock_widget()
        top_level_dock_widget = self.top_level_dock_widget()

        if dock_area is not None:
            drop_overlay = self.d.dock_manager.dock_area_overlay()
            drop_overlay.set_allowed_areas(DockWidgetArea.all_dock_areas)
            drop_area = drop_overlay.show_overlay(dock_area)
            if (container_drop_area not in (
                    DockWidgetArea.invalid, drop_area)):
                drop_area = DockWidgetArea.invalid

            if drop_area != DockWidgetArea.invalid:
                logger.debug('Dock Area Drop Content: %s', drop_area)
                self.d.drop_into_section(floating_widget, dock_area, drop_area)

        # mouse is over container
        if DockWidgetArea.invalid == drop_area:
            drop_area = container_drop_area
            logger.debug('Container Drop Content: %s', drop_area)
            if drop_area != DockWidgetArea.invalid:
                self.d.drop_into_container(floating_widget, drop_area)

        # If there was a top level widget before the drop, then it is not top
        # level widget anymore
        if top_level_dock_widget is not None:
            top_level_dock_widget.emit_top_level_changed(False)

        # If we drop a floating widget with only one single dock widget, then we
        # drop a top level widget that changes from floating to docked now
        if floating_top_level_dock_widget is not None:
            floating_top_level_dock_widget.emit_top_level_changed(False)

    def add_dock_area(self, dock_area_widget: DockAreaWidget,
                      area: DockWidgetArea = DockWidgetArea.center):
        '''
        Adds the given dock area to this container widget

        Parameters
        ----------
        dock_area_widget : DockAreaWidget
        area : DockWidgetArea
        '''
        container = dock_area_widget.dock_container()
        if container and container is not self:
            container.remove_dock_area(dock_area_widget)

        self.d.add_dock_area(dock_area_widget, area)

    def remove_dock_area(self, area: DockAreaWidget):
        '''
        Removes the given dock area from this container

        Parameters
        ----------
        area : DockAreaWidget
        '''
        def emit_and_exit():
            top_level_widget = self.top_level_dock_widget()

            # Updated the title bar visibility of the dock widget if there is only
            # one single visible dock widget
            emit_top_level_event_for_widget(top_level_widget, True)
            self.dump_layout()
            self.d.emit_dock_areas_removed()

        logger.debug('DockContainerWidget.removeDockArea')
        if area not in self.d.dock_areas:
            logger.error('Area %s not found in DockContainerWidget %s?',
                         area, self)
            return

        area.view_toggled.disconnect(self.d.on_dock_area_view_toggled)
        self.d.dock_areas.remove(area)
        splitter = find_parent(DockSplitter, area)

        # Remove are from parent splitter and recursively hide tree of parent
        # splitters if it has no visible content
        logger.debug('area setParent %s None', area)
        area.setParent(None)
        hide_empty_parent_splitters(splitter)

        # Remove this area from cached areas
        for _area, _widget in self.d.last_added_area_cache.items():
            if _widget is splitter:
                self.d.last_added_area_cache[_area] = None

        # If splitter has more than 1 widgets, we are finished and can leave
        if splitter.count() > 1:
            return emit_and_exit()

        # If this is the RootSplitter we need to remove empty splitters to
        # avoid too many empty splitters
        if splitter is self.d.root_splitter:
            logger.debug('Removed from RootSplitter')

            # If splitter is empty, we are finished
            if not splitter.count():
                splitter.hide()
                return emit_and_exit()

            child_splitter = splitter.widget(0)

            # If the one and only content widget of the splitter is not a splitter
            # then we are finished
            if not isinstance(child_splitter, QSplitter):
                return emit_and_exit()

            # We replace the superfluous RootSplitter with the ChildSplitter
            logger.debug('child_splitter setParent %s None', child_splitter)
            child_splitter.setParent(None)
            self.d.layout.replaceWidget(splitter, child_splitter)
            self.d.root_splitter = child_splitter

            logger.debug('RootSplitter replaced by child splitter')

        elif splitter.count() == 1:
            logger.debug('Replacing splitter with content')
            parent_splitter = find_parent(QSplitter, splitter)
            sizes = parent_splitter.sizes()
            widget = splitter.widget(0)
            logger.debug('widget setParent to dock container %s %s', widget, self)
            widget.setParent(self)
            replace_splitter_widget(parent_splitter, splitter, widget)
            parent_splitter.setSizes(sizes)

        splitter.deleteLater()
        splitter = None

        return emit_and_exit()

    def save_state(self, stream: QXmlStreamWriter):
        '''
        Saves the state into the given stream

        Parameters
        ----------
        stream : QXmlStreamWriter
        '''
        logger.debug('DockContainerWidget.saveState isFloating %s',
                     self.is_floating())
        stream.writeStartElement("Container")
        stream.writeAttribute("Floating", '1' if self.is_floating() else '0')
        if self.is_floating():
            floating_widget = self.floating_widget()
            geometry = floating_widget.saveGeometry()
            stream.writeTextElement("Geometry", geometry.toHex(' '))
        self.d.save_child_nodes_state(stream, self.d.root_splitter)
        stream.writeEndElement()

    def restore_state(self, stream: QXmlStreamReader, testing: bool = False) -> bool:
        '''
        Restores the state from given stream.

        Parameters
        ----------
        stream : QXmlStreamReader
        testing : bool
            If Testing is true, the function only parses the data from the
            given stream but does not restore anything. You can use this check
            for faulty files before you start restoring the state

        Returns
        -------
        value : bool
        '''
        is_floating = bool(int(stream.attributes().value("Floating")))
        logger.debug('Restore DockContainerWidget Floating %s', is_floating)

        if not testing:
            self.d._visible_dock_area_count = -1

            # invalidate the dock area count and clear the area cache
            self.d.dock_areas.clear()
            self.d.last_added_area_cache.clear()

        if is_floating:
            logger.debug('Restore floating widget')
            if not stream.readNextStartElement() or stream.name() != "Geometry":
                return False

            geometry_string = stream.readElementText(
                QXmlStreamReader.ErrorOnUnexpectedElement)

            geometry = QByteArray.fromHex(geometry_string)
            if geometry.isEmpty():
                return False

            if not testing:
                floating_widget = self.floating_widget()
                floating_widget.restoreGeometry(geometry)

        res, new_root_splitter = self.d.restore_child_nodes(stream, testing)
        if not res:
            return False

        if testing:
            return True

        # If the root splitter is empty, rostoreChildNodes returns a 0 pointer
        # and we need to create a new empty root splitter
        if not new_root_splitter:
            new_root_splitter = self.d.new_splitter(Qt.Horizontal)

        self.d.layout.replaceWidget(self.d.root_splitter, new_root_splitter)
        old_root = self.d.root_splitter
        self.d.root_splitter = new_root_splitter
        old_root.deleteLater()
        return True

    def last_added_dock_area_widget(self, area: DockWidgetArea) -> DockAreaWidget:
        '''
        This function returns the last added dock area widget for the given
        area identifier or 0 if no dock area widget has been added for the
        given area

        Parameters
        ----------
        area : DockWidgetArea

        Returns
        -------
        value : DockAreaWidget
        '''
        return self.d.last_added_area_cache.get(area, None)

    def has_top_level_dock_widget(self) -> bool:
        '''
        This function returns true if this dock area has only one single
        visible dock widget. A top level widget is a real floating widget. Only
        the isFloating() function of top level widgets may returns true.

        Returns
        -------
        value : bool
        '''
        if not self.is_floating():
            return False

        dock_areas = self.opened_dock_areas()
        if len(dock_areas) != 1:
            return False

        return dock_areas[0].open_dock_widgets_count() == 1

    def top_level_dock_widget(self) -> 'DockWidget':
        '''
        If hasSingleVisibleDockWidget() returns true, this function returns the
        one and only visible dock widget. Otherwise it returns a nullptr.

        Returns
        -------
        value : DockWidget
        '''
        top_level_dock_area = self.top_level_dock_area()
        if not top_level_dock_area:
            return None

        dock_widgets = top_level_dock_area.opened_dock_widgets()
        if len(dock_widgets) != 1:
            return None

        return dock_widgets[0]

    def top_level_dock_area(self) -> DockAreaWidget:
        '''
        Returns the top level dock area.

        Returns
        -------
        value : DockAreaWidget
        '''
        if not self.is_floating():
            return None

        dock_areas = self.opened_dock_areas()
        if len(dock_areas) != 1:
            return None

        return dock_areas[0]

    def dock_widgets(self) -> list:
        '''
        This function returns a list of all dock widgets in this floating
        widget. It may be possible, depending on the implementation, that dock
        widgets, that are not visible to the user have no parent widget.
        Therefore simply calling findChildren() would not work here. Therefore
        this function iterates over all dock areas and creates a list that
        contains all dock widgets returned from all dock areas.

        Returns
        -------
        value : list
        '''
        return [widget
                for dock_area in self.d.dock_areas
                for widget in dock_area.dock_widgets()
                ]

    def add_dock_widget(self, area: DockWidgetArea, dockwidget: 'DockWidget',
                        dock_area_widget: DockAreaWidget = None) -> DockAreaWidget:
        '''
        Adds dockwidget into the given area. If DockAreaWidget is not null,
        then the area parameter indicates the area into the DockAreaWidget. If
        DockAreaWidget is null, the Dockwidget will be dropped into the
        container.

        Parameters
        ----------
        area : DockWidgetArea
        dockwidget : DockWidget
        dock_area_widget : DockAreaWidget

        Returns
        -------
        value : DockAreaWidget
        '''
        old_dock_area = dockwidget.dock_area_widget()
        if old_dock_area is not None:
            old_dock_area.remove_dock_widget(dockwidget)

        dockwidget.set_dock_manager(self.d.dock_manager)
        if dock_area_widget is not None:
            return self.d.dock_widget_into_dock_area(area, dockwidget, dock_area_widget)
        return self.d.dock_widget_into_container(area, dockwidget)

    def remove_dock_widget(self, widget: 'DockWidget'):
        '''
        Removes a given DockWidget

        Parameters
        ----------
        widget : DockWidget
        '''
        area = widget.dock_area_widget()
        if area is not None:
            area.remove_dock_widget(widget)

    def z_order_index(self) -> int:
        '''
        Returns the current zOrderIndex

        Returns
        -------
        value : unsigned int
        '''
        return self.d.z_order_index

    def is_in_front_of(self, other: 'DockContainerWidget') -> bool:
        '''
        This function returns true if this container widgets z order index is
        higher than the index of the container widget given in Other parameter

        Parameters
        ----------
        other : DockContainerWidget

        Returns
        -------
        value : bool
        '''
        return self.z_order_index() > other.z_order_index()

    def dock_area_at(self, global_pos: QPoint) -> DockAreaWidget:
        '''
        Returns the dock area at teh given global position or 0 if there is no
        dock area at this position

        Parameters
        ----------
        global_pos : QPoint

        Returns
        -------
        value : DockAreaWidget
        '''
        for dock_area in self.d.dock_areas:
            pos = dock_area.mapFromGlobal(global_pos)
            if dock_area.isVisible() and dock_area.rect().contains(pos):
                return dock_area

        return None

    def dock_area(self, index: int) -> DockAreaWidget:
        '''
        Returns the dock area at the given Index or 0 if the index is out of range

        Parameters
        ----------
        index : int

        Returns
        -------
        value : DockAreaWidget
        '''
        try:
            return self.d.dock_areas[index]
        except IndexError:
            return None

    def opened_dock_areas(self) -> list:
        '''
        Returns the list of dock areas that are not closed If all dock widgets
        in a dock area are closed, the dock area will be closed

        Returns
        -------
        value : list
        '''
        return [dock_area
                for dock_area in self.d.dock_areas
                if not dock_area.isHidden()
                ]

    def dock_area_count(self) -> int:
        '''
        Returns the number of dock areas in this container

        Returns
        -------
        value : int
        '''
        return len(self.d.dock_areas)

    def visible_dock_area_count(self) -> int:
        '''
        Returns the number of visible dock areas

        Returns
        -------
        value : int
        '''
        return len([dock_area
                    for dock_area in self.d.dock_areas
                    if not dock_area.isHidden()
                    ])

        # TODO_UPSTREAM Cache or precalculate this to speed it up because it is used during
        # movement of floating widget
        # return d.visible_dock_area_count()

    def is_floating(self) -> bool:
        '''
        This function returns true, if this container is in a floating widget

        Returns
        -------
        value : bool
        '''
        return self.d.is_floating

    def dump_layout(self):
        '''
        Dumps the layout for debugging purposes
        '''
        if not logger.isEnabledFor(logging.DEBUG):
            return

        logger.debug("--------------------------")
        self.d.dump_recursive(0, self.d.root_splitter)
        logger.debug("--------------------------\n\n")

    def features(self) -> DockWidgetFeature:
        '''
        This functions returns the dock widget features of all dock widget in
        this container. A bitwise and is used to combine the flags of all dock
        widgets. That means, if only dock widget does not support a certain
        flag, the whole dock are does not support the flag.

        Returns
        -------
        value : DockWidgetFeature
        '''
        features = DockWidgetFeature.all_features
        for dock_area in self.d.dock_areas:
            features &= dock_area.features()
        return features

    def floating_widget(self) -> 'FloatingDockContainer':
        '''
        If this dock container is in a floating widget, this function returns
        the floating widget. Else, it returns a nullptr.

        Returns
        -------
        value : FloatingDockContainer
        '''
        from .floating_dock_container import FloatingDockContainer
        return find_parent(FloatingDockContainer, self)

    def close_other_areas(self, keep_open_area: DockAreaWidget):
        '''
        Call this function to close all dock areas except the KeepOpenArea

        Parameters
        ----------
        keep_open_area : DockAreaWidget
        '''
        for dock_area in self.d.dock_areas:
            if dock_area != keep_open_area and DockWidgetFeature.closable in dock_area.features():
                dock_area.close_area()

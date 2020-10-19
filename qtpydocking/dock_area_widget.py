import logging
from typing import TYPE_CHECKING, Optional

from qtpy.QtCore import QRect, QXmlStreamWriter, Signal
from qtpy.QtWidgets import QAbstractButton, QAction, QBoxLayout, QFrame

from .util import (find_parent, DEBUG_LEVEL, hide_empty_parent_splitters,
                   emit_top_level_event_for_widget)
from .enums import TitleBarButton, DockWidgetFeature
from .dock_area_layout import DockAreaLayout

if TYPE_CHECKING:
    from . import (DockContainerWidget, DockManager, DockWidget, DockWidgetTab,
                   DockAreaTabBar, DockAreaTitleBar)

logger = logging.getLogger(__name__)


class DockAreaWidgetPrivate:
    public: 'DockAreaWidget'
    layout: QBoxLayout
    contents_layout: DockAreaLayout
    title_bar: 'DockAreaTitleBar'
    dock_manager: 'DockManager'
    update_title_bar_buttons: bool

    def __init__(self, public):
        '''
        Private data constructor

        Parameters
        ----------
        public : DockAreaWidget
        '''
        self.public = public
        self.layout = None
        self.contents_layout = None
        self.title_bar = None
        self.dock_manager = None
        self.update_title_bar_buttons = False

    def create_title_bar(self):
        '''
        Creates the layout for top area with tabs and close button
        '''
        from .dock_area_title_bar import DockAreaTitleBar
        self.title_bar = DockAreaTitleBar(self.public)
        self.layout.addWidget(self.title_bar)

        tab_bar = self.tab_bar()
        tab_bar.tab_close_requested.connect(
            self.public.on_tab_close_requested)
        self.title_bar.tab_bar_clicked.connect(self.public.set_current_index)
        tab_bar.tab_moved.connect(self.public.reorder_dock_widget)

    def dock_widget_at(self, index: int) -> 'DockWidget':
        '''
        Returns the dock widget with the given index

        Parameters
        ----------
        index : int

        Returns
        -------
        value : DockWidget
        '''
        return self.contents_layout.widget(index)

    def tab_widget_at(self, index: int) -> 'DockWidgetTab':
        '''
        Convenience function to ease title widget access by index

        Parameters
        ----------
        index : int

        Returns
        -------
        value : DockWidgetTab
        '''
        return self.dock_widget_at(index).tab_widget()

    def dock_widget_tab_action(self, dock_widget: 'DockWidget') -> QAction:
        '''
        Returns the tab action of the given dock widget

        Parameters
        ----------
        dock_widget : DockWidget

        Returns
        -------
        value : QAction
        '''
        return dock_widget.property('action')

    def dock_widget_index(self, dock_widget: 'DockWidget') -> int:
        '''
        Returns the index of the given dock widget

        Parameters
        ----------
        dock_widget : DockWidget

        Returns
        -------
        value : int
        '''
        return dock_widget.property('index')

    def tab_bar(self) -> 'DockAreaTabBar':
        '''
        Convenience function for tabbar access

        Returns
        -------
        value : DockAreaTabBar
        '''
        return self.title_bar.tab_bar()

    def update_title_bar_button_states(self):
        '''
        Udpates the enable state of the close/detach buttons
        '''
        if self.public.isHidden():
            self.update_title_bar_buttons = True
            return

        close_button = self.title_bar.button(TitleBarButton.close)
        close_button.setEnabled(self.public.closable)

        undock_button = self.title_bar.button(TitleBarButton.undock)
        undock_button.setEnabled(self.public.floatable)

        self.update_title_bar_buttons = False


class DockAreaWidget(QFrame):
    # This signal is emitted when user clicks on a tab at an index.
    tab_bar_clicked = Signal(int)
    # This signal is emitted when the tab bar's current tab is about to be
    # changed. The new current has the given index, or -1 if there isn't a new one.
    current_changing = Signal(int)

    # This signal is emitted when the tab bar's current tab changes. The new
    # current has the given index, or -1 if there isn't a new one
    current_changed = Signal(int)

    # This signal is emitted if the visibility of this dock area is toggled via
    # toggle view function
    view_toggled = Signal(bool)

    def __init__(self, dock_manager: 'DockManager',
                 parent: 'DockContainerWidget'):
        '''
        Default Constructor

        Parameters
        ----------
        dock_manager : DockManager
        parent : DockContainerWidget
        '''
        super().__init__(parent)
        self.d = DockAreaWidgetPrivate(self)
        self.d.dock_manager = dock_manager
        self.d.layout = QBoxLayout(QBoxLayout.TopToBottom)
        self.d.layout.setContentsMargins(0, 0, 0, 0)
        self.d.layout.setSpacing(0)
        self.setLayout(self.d.layout)
        self.d.create_title_bar()
        self.d.contents_layout = DockAreaLayout(self.d.layout)

    def __repr__(self):
        return f'<{self.__class__.__name__}>'

    def on_tab_close_requested(self, index: int):
        '''
        On tab close requested

        Parameters
        ----------
        index : int
        '''
        logger.debug('DockAreaWidget.onTabCloseRequested %s', index)
        self.dock_widget(index).toggle_view(False)

    def reorder_dock_widget(self, from_index: int, to_index: int):
        '''
        Reorder the index position of DockWidget at fromIndx to toIndex if a
        tab in the tabbar is dragged from one index to another one

        Parameters
        ----------
        from_index : int
        to_index : int
        '''
        logger.debug('DockAreaWidget.reorderDockWidget')
        if (from_index >= self.d.contents_layout.count() or
                from_index < 0 or
                to_index >= self.d.contents_layout.count() or
                to_index < 0 or
                from_index == to_index):
            logger.debug('Invalid index for tab movement %s:%s', from_index,
                         to_index)
            return

        widget = self.d.contents_layout.widget(from_index)
        self.d.contents_layout.remove_widget(widget)
        self.d.contents_layout.insert_widget(to_index, widget)
        self.set_current_index(to_index)

    def insert_dock_widget(self, index: int, dock_widget: 'DockWidget',
                           activate: bool = True):
        '''
        Inserts a dock widget into dock area.

        All dockwidgets in the dock area tabified in a stacked layout with
        tabs. The index indicates the index of the new dockwidget in the tabbar
        and in the stacked layout. If the Activate parameter is true, the new
        DockWidget will be the active one in the stacked layout

        Parameters
        ----------
        index : int
        dock_widget : DockWidget
        activate : bool, optional
        '''
        self.d.contents_layout.insert_widget(index, dock_widget)
        dock_widget.tab_widget().set_dock_area_widget(self)
        tab_widget = dock_widget.tab_widget()

        # Inserting the tab will change the current index which in turn will
        # make the tab widget visible in the slot
        tab_bar = self.d.tab_bar()
        tab_bar.blockSignals(True)
        tab_bar.insert_tab(index, tab_widget)
        tab_bar.blockSignals(False)

        tab_widget.setVisible(not dock_widget.is_closed())
        dock_widget.setProperty('index', index)
        if activate:
            self.set_current_index(index)

        dock_widget.set_dock_area(self)
        self.d.update_title_bar_button_states()

    def add_dock_widget(self, dock_widget: 'DockWidget'):
        '''
        Add a new dock widget to dock area. All dockwidgets in the dock area tabified in a stacked layout with tabs

        Parameters
        ----------
        dock_widget : DockWidget
        '''
        self.insert_dock_widget(self.d.contents_layout.count(), dock_widget)

    def remove_dock_widget(self, dock_widget: 'DockWidget'):
        '''
        Removes the given dock widget from the dock area

        Parameters
        ----------
        dock_widget : DockWidget
        '''
        logger.debug('DockAreaWidget.removeDockWidget')
        next_open_dock_widget = self.next_open_dock_widget(dock_widget)
        self.d.contents_layout.remove_widget(dock_widget)
        tab_widget = dock_widget.tab_widget()
        tab_widget.hide()
        self.d.tab_bar().remove_tab(tab_widget)
        dock_container = self.dock_container()
        if next_open_dock_widget is not None:
            self.set_current_dock_widget(next_open_dock_widget)
        elif (self.d.contents_layout.is_empty() and
                  dock_container.dock_area_count() > 1):
            logger.debug('Dock Area empty')
            dock_container.remove_dock_area(self)
            self.deleteLater()
        else:
            # if contents layout is not empty but there are no more open dock
            # widgets, then we need to hide the dock area because it does not
            # contain any visible content
            self.hide_area_with_no_visible_content()

        self.d.update_title_bar_button_states()
        self.update_title_bar_visibility()
        top_level_dock_widget = dock_container.top_level_dock_widget()
        if top_level_dock_widget is not None:
            top_level_dock_widget.emit_top_level_changed(True)

        if DEBUG_LEVEL > 0:
            dock_container.dump_layout()

    def toggle_dock_widget_view(self, dock_widget: 'DockWidget', open_: bool):
        '''
        Called from dock widget if it is opened or closed

        Parameters
        ----------
        dock_widget : DockWidget
            Unused
        open : bool
            Unused
        '''
        #pylint: disable=unused-argument
        self.update_title_bar_visibility()

    def next_open_dock_widget(self, dock_widget: 'DockWidget'
                              ) -> Optional['DockWidget']:
        '''
        This is a helper function to get the next open dock widget to activate
        if the given DockWidget will be closed or removed. The function returns
        the next widget that should be activated or nullptr in case there are
        no more open widgets in this area.

        Parameters
        ----------
        dock_widget : DockWidget

        Returns
        -------
        value : DockWidget
        '''
        open_dock_widgets = self.opened_dock_widgets()
        count = len(open_dock_widgets)
        if count > 1 or (count == 1 and open_dock_widgets[0] != dock_widget):
            if open_dock_widgets[-1] == dock_widget:
                next_dock_widget = open_dock_widgets[-2]
            else:
                next_index = open_dock_widgets.index(dock_widget)+1
                next_dock_widget = open_dock_widgets[next_index]
            return next_dock_widget
        return None

    def index(self, dock_widget: 'DockWidget') -> int:
        '''
        Returns the index of the given DockWidget in the internal layout

        Parameters
        ----------
        dock_widget : DockWidget

        Returns
        -------
        value : int
        '''
        return self.d.contents_layout.index_of(dock_widget)

    def hide_area_with_no_visible_content(self):
        '''
        Call this function, if you already know, that the dock does not contain
        any visible content (any open dock widgets).
        '''
        self.toggle_view(False)

        # Hide empty parent splitters
        from .dock_splitter import DockSplitter
        splitter = find_parent(DockSplitter, self)
        hide_empty_parent_splitters(splitter)

        # Hide empty floating widget
        container = self.dock_container()
        if not container.is_floating():
            return

        self.update_title_bar_visibility()
        top_level_widget = container.top_level_dock_widget()
        floating_widget = container.floating_widget()
        if top_level_widget is not None:
            floating_widget.update_window_title()
            emit_top_level_event_for_widget(top_level_widget, True)

        elif not container.opened_dock_areas():
            floating_widget.hide()

    def update_title_bar_visibility(self):
        '''
        Updates the dock area layout and components visibility
        '''
        container = self.dock_container()
        if not container:
            return

        if self.d.title_bar:
            visible = not container.is_floating() or not container.has_top_level_dock_widget()
            self.d.title_bar.setVisible(visible)

    def internal_set_current_dock_widget(self, dock_widget: 'DockWidget'):
        '''
        This is the internal private function for setting the current widget.
        This function is called by the public setCurrentDockWidget() function
        and by the dock manager when restoring the state

        Parameters
        ----------
        dock_widget : DockWidget
        '''
        index = self.index(dock_widget)
        if index < 0:
            return

        self.set_current_index(index)

    def mark_title_bar_menu_outdated(self):
        '''
        Marks tabs menu to update
        '''
        if self.d.title_bar:
            self.d.title_bar.mark_tabs_menu_outdated()

    def toggle_view(self, open_: bool):
        '''
        Toggle view

        Parameters
        ----------
        open_ : bool
        '''
        self.setVisible(open_)
        self.view_toggled.emit(open_)

    def dock_manager(self) -> 'DockManager':
        '''
        Returns the dock manager object this dock area belongs to

        Returns
        -------
        value : DockManager
        '''
        return self.d.dock_manager

    def dock_container(self) -> 'DockContainerWidget':
        '''
        Returns the dock container widget this dock area widget belongs to or 0 if there is no

        Returns
        -------
        value : DockContainerWidget
        '''
        from .dock_container_widget import DockContainerWidget
        return find_parent(DockContainerWidget, self)

    def title_bar_geometry(self) -> QRect:
        '''
        Returns the rectangle of the title area

        Returns
        -------
        value : QRect
        '''
        return self.d.title_bar.geometry()

    def content_area_geometry(self) -> QRect:
        '''
        Returns the rectangle of the content

        Returns
        -------
        value : QRect
        '''
        return self.d.contents_layout.geometry()

    def dock_widgets_count(self) -> int:
        '''
        Returns the number of dock widgets in this area

        Returns
        -------
        value : int
        '''
        return self.d.contents_layout.count()

    def dock_widgets(self) -> list:
        '''
        Returns a list of all dock widgets in this dock area. This list
        contains open and closed dock widgets.

        Returns
        -------
        value : list of DockWidget
        '''
        return [
            self.dock_widget(i)
            for i in range(self.d.contents_layout.count())
        ]

    def open_dock_widgets_count(self) -> int:
        '''
        Returns the number of dock widgets in this area

        Returns
        -------
        value : int
        '''
        return len(self.opened_dock_widgets())

    def opened_dock_widgets(self) -> list:
        '''
        Returns a list of dock widgets that are not closed

        Returns
        -------
        value : list of DockWidget
        '''
        return [w for w in self.dock_widgets()
                if not w.is_closed()
                ]

    def dock_widget(self, index: int) -> 'DockWidget':
        '''
        Returns a dock widget by its index

        Parameters
        ----------
        index : int

        Returns
        -------
        value : DockWidget
        '''
        return self.d.contents_layout.widget(index)

    def current_index(self) -> int:
        '''
        Returns the index of the current active dock widget or -1 if there are
        is no active dock widget (ie.e if all dock widgets are closed)

        Returns
        -------
        value : int
        '''
        return self.d.contents_layout.current_index()

    def index_of_first_open_dock_widget(self) -> int:
        '''
        Returns the index of the first open dock widgets in the list of dock
        widgets.

        This function is here for performance reasons. Normally it would be
        possible to take the first dock widget from the list returned by
        openedDockWidgets() function. But that function enumerates all dock widgets
        while this functions stops after the first open dock widget. If there are no
        open dock widgets, the function returns -1.

        Returns
        -------
        value : int
        '''
        for i in range(self.d.contents_layout.count()):
            if not self.dock_widget(i).is_closed():
                return i

        return -1

    def current_dock_widget(self) -> Optional['DockWidget']:
        '''
        Returns the current active dock widget or a nullptr if there is no
        active dock widget (i.e. if all dock widgets are closed)

        Returns
        -------
        value : DockWidget
        '''
        current_index = self.current_index()
        if current_index < 0:
            return None

        return self.dock_widget(current_index)

    def set_current_dock_widget(self, dock_widget: 'DockWidget'):
        '''
        Shows the tab with the given dock widget

        Parameters
        ----------
        dock_widget : DockWidget
        '''
        if self.dock_manager().is_restoring_state():
            return

        self.internal_set_current_dock_widget(dock_widget)

    def save_state(self, stream: QXmlStreamWriter):
        '''
        Saves the state into the given stream

        Parameters
        ----------
        stream : QXmlStreamWriter
        '''
        stream.writeStartElement("Area")
        stream.writeAttribute("Tabs", str(self.d.contents_layout.count()))
        current_dock_widget = self.current_dock_widget()
        name = current_dock_widget.objectName() if current_dock_widget else ''
        stream.writeAttribute("Current", name)
        logger.debug('DockAreaWidget.saveState TabCount: %s current: %s',
                     self.d.contents_layout.count(), name)

        for i in range(self.d.contents_layout.count()):
            self.dock_widget(i).save_state(stream)

        stream.writeEndElement()

    @property
    def closable(self):
        '''
        Is the dock area widget closable?
        '''
        return DockWidgetFeature.closable in self.features()

    @property
    def floatable(self):
        '''
        Is the dock area widget floatable?
        '''
        return DockWidgetFeature.floatable in self.features()

    def features(self) -> DockWidgetFeature:
        '''
        This functions returns the dock widget features of all dock widget in
        this area. A bitwise and is used to combine the flags of all dock
        widgets. That means, if only dock widget does not support a certain
        flag, the whole dock are does not support the flag.

        Returns
        -------
        value : DockWidgetFeature
        '''
        features = DockWidgetFeature.all_features
        for dock_widget in self.dock_widgets():
            features &= dock_widget.features()

        return features

    def title_bar_button(self, which: TitleBarButton) -> QAbstractButton:
        '''
        Returns the title bar button corresponding to the given title bar button identifier

        Parameters
        ----------
        which : TitleBarButton

        Returns
        -------
        value : QAbstractButton
        '''
        return self.d.title_bar.button(which)

    def setVisible(self, visible: bool):
        '''
        Update the close button if visibility changed

        Parameters
        ----------
        visible : bool
        '''
        super().setVisible(visible)
        if self.d.update_title_bar_buttons:
            self.d.update_title_bar_button_states()

    def set_current_index(self, index: int):
        '''
        This activates the tab for the given tab index. If the dock widget for
        the given tab is not visible, the this function call will make it visible.

        Parameters
        ----------
        index : int
        '''
        tab_bar = self.d.tab_bar()
        if index < 0 or index > (tab_bar.count()-1):
            logger.warning('Invalid index %s', index)
            return

        self.current_changing.emit(index)
        tab_bar.set_current_index(index)
        self.d.contents_layout.set_current_index(index)
        self.d.contents_layout.current_widget().show()
        self.current_changed.emit(index)

    def close_area(self):
        '''
        Closes the dock area and all dock widgets in this area
        '''
        for dock_widget in self.opened_dock_widgets():
            dock_widget.toggle_view(False)

    def close_other_areas(self):
        '''
        This function closes all other areas except of this area
        '''
        self.dock_container().close_other_areas(self)

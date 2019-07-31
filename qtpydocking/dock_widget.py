import logging
from typing import TYPE_CHECKING, Optional

from qtpy.QtCore import QEvent, QSize, QXmlStreamWriter, Qt, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (QAction, QBoxLayout, QFrame, QScrollArea,
                            QSplitter, QToolBar, QWidget)

from .enums import (DockWidgetFeature, WidgetState, ToggleViewActionMode,
                    InsertMode)
from .util import find_parent, emit_top_level_event_for_widget

if TYPE_CHECKING:
    from . import DockAreaWidget, DockManager, DockWidgetTab

logger = logging.getLogger(__name__)


class DockWidgetPrivate:
    public: 'DockWidget'
    layout: QBoxLayout
    widget: QWidget
    tab_widget: 'DockWidgetTab'
    features: DockWidgetFeature
    dock_manager: 'DockManager'
    dock_area: 'DockAreaWidget'
    toggle_view_action: QAction
    closed: bool
    scroll_area: QScrollArea
    tool_bar: QToolBar
    tool_bar_style_docked: int
    tool_bar_style_floating: int
    tool_bar_icon_size_docked: QSize
    tool_bar_icon_size_floating: QSize
    is_floating_top_level: bool

    def __init__(self, public: 'DockWidget'):
        self.public = public
        self.layout = None
        self.widget = None
        self.tab_widget = None
        self.features = DockWidgetFeature.all_features
        self.dock_manager = None
        self.dock_area = None
        self.toggle_view_action = None
        self.closed = False
        self.scroll_area = None
        self.tool_bar = None
        self.tool_bar_style_docked = Qt.ToolButtonIconOnly
        self.tool_bar_style_floating = Qt.ToolButtonTextUnderIcon
        self.tool_bar_icon_size_docked = QSize(16, 16)
        self.tool_bar_icon_size_floating = QSize(24, 24)
        self.is_floating_top_level = False

    def show_dock_widget(self):
        '''
        Show dock widget
        '''
        from .floating_dock_container import FloatingDockContainer
        if not self.dock_area:
            floating_widget = FloatingDockContainer(dock_widget=self.public)
            floating_widget.resize(self.public.size())
            floating_widget.show()
            return

        self.dock_area.toggle_view(True)
        self.dock_area.set_current_dock_widget(self.public)
        self.tab_widget.show()

        splitter = find_parent(QSplitter, self.dock_area)

        while splitter and not splitter.isVisible():
            splitter.show()
            splitter = find_parent(QSplitter, splitter)

        container = self.dock_area.dock_container()
        if container.is_floating():
            floating_widget = find_parent(FloatingDockContainer, container)
            floating_widget.show()

    def hide_dock_widget(self):
        '''
        Hide dock widget.
        '''
        self.tab_widget.hide()
        self.update_parent_dock_area()

    def update_parent_dock_area(self):
        '''
        Hides a dock area if all dock widgets in the area are closed. This
        function updates the current selected tab and hides the parent dock
        area if it is empty
        '''
        if not self.dock_area:
            return

        next_dock_widget = self.dock_area.next_open_dock_widget(self.public)
        if next_dock_widget is not None:
            self.dock_area.set_current_dock_widget(next_dock_widget)
        else:
            self.dock_area.hide_area_with_no_visible_content()

    def setup_tool_bar(self):
        '''
        Setup the top tool bar
        '''
        self.tool_bar = QToolBar(self.public)
        self.tool_bar.setObjectName("dockWidgetToolBar")
        self.layout.insertWidget(0, self.tool_bar)
        self.tool_bar.setIconSize(QSize(16, 16))
        self.tool_bar.toggleViewAction().setEnabled(False)
        self.tool_bar.toggleViewAction().setVisible(False)
        self.public.top_level_changed.connect(self.public.set_toolbar_floating_style)

    def setup_scroll_area(self):
        '''
        Setup the main scroll area
        '''
        self.scroll_area = QScrollArea(self.public)
        self.scroll_area.setObjectName("dockWidgetScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.layout.addWidget(self.scroll_area)


class DockWidget(QFrame):
    # This signal is emitted if the dock widget is opened or closed
    view_toggled = Signal(bool)
    # This signal is emitted if the dock widget is closed
    closed = Signal()
    # This signal is emitted if the window title of this dock widget changed
    title_changed = Signal(str)
    # This signal is emitted when the floating property changes. The topLevel
    # parameter is true if the dock widget is now floating; otherwise it is
    # false.
    top_level_changed = Signal(bool)

    def __init__(self, title: str, parent: QWidget = None):
        '''
        This constructor creates a dock widget with the given title. The title
        is the text that is shown in the window title when the dock widget is
        floating and it is the title that is shown in the titlebar or the tab
        of this dock widget if it is tabified. The object name of the dock
        widget is also set to the title. The object name is required by the
        dock manager to properly save and restore the state of the dock widget.
        That means, the title needs to be unique. If your title is not unique
        or if you would like to change the title during runtime, you need to
        set a unique object name explicitely by calling setObjectName() after
        construction. Use the layoutFlags to configure the layout of the dock
        widget.

        Parameters
        ----------
        title : str
        parent : QWidget
        '''
        super().__init__(parent)
        self.d = DockWidgetPrivate(self)
        self.d.layout = QBoxLayout(QBoxLayout.TopToBottom)
        self.d.layout.setContentsMargins(0, 0, 0, 0)
        self.d.layout.setSpacing(0)
        self.setLayout(self.d.layout)
        self.setWindowTitle(title)
        self.setObjectName(title)

        from .dock_widget_tab import DockWidgetTab
        self.d.tab_widget = DockWidgetTab(dock_widget=self, parent=None)  # TODO: parent?
        self.d.toggle_view_action = QAction(title, self)
        self.d.toggle_view_action.setCheckable(True)
        self.d.toggle_view_action.triggered.connect(self.toggle_view)
        self.set_toolbar_floating_style(False)

    def __repr__(self):
        return f'<{self.__class__.__name__} title={self.windowTitle()!r}>'

    def set_toolbar_floating_style(self, floating: bool):
        '''
        Adjusts the toolbar icon sizes according to the floating state

        Parameters
        ----------
        top_level : bool
        '''
        if not self.d.tool_bar:
            return

        icon_size = (self.d.tool_bar_icon_size_floating
                     if floating
                     else self.d.tool_bar_icon_size_docked
                     )
        if icon_size != self.d.tool_bar.iconSize():
            self.d.tool_bar.setIconSize(icon_size)

        button_style = (self.d.tool_bar_style_floating
                        if floating
                        else self.d.tool_bar_style_docked
                        )
        if button_style != self.d.tool_bar.toolButtonStyle():
            self.d.tool_bar.setToolButtonStyle(button_style)

    def set_dock_manager(self, dock_manager: 'DockManager'):
        '''
        Assigns the dock manager that manages this dock widget

        Parameters
        ----------
        dock_manager : DockManager
        '''
        self.d.dock_manager = dock_manager

    def set_dock_area(self, dock_area: 'DockAreaWidget'):
        '''
        If this dock widget is inserted into a dock area, the dock area will be
        registered on this widget via this function. If a dock widget is
        removed from a dock area, this function will be called with nullptr
        value.

        Parameters
        ----------
        dock_area : DockAreaWidget
        '''
        self.d.dock_area = dock_area
        self.d.toggle_view_action.setChecked(dock_area is not None and not self.is_closed())

    def set_toggle_view_action_checked(self, checked: bool):
        '''
        This function changes the toggle view action without emitting any signal

        Parameters
        ----------
        checked : bool
        '''
        action = self.d.toggle_view_action
        action.blockSignals(True)
        action.setChecked(checked)
        action.blockSignals(False)

    def save_state(self, stream: QXmlStreamWriter):
        '''
        Saves the state into the given stream

        Parameters
        ----------
        stream : QXmlStreamWriter
        '''
        stream.writeStartElement("Widget")
        stream.writeAttribute("Name", self.objectName())
        stream.writeAttribute("Closed", '1' if self.d.closed else '0')
        stream.writeEndElement()

    def flag_as_unassigned(self):
        '''
        This is a helper function for the dock manager to flag this widget as
        unassigned. When calling the restore function, it may happen, that the
        saved state contains less dock widgets then currently available. All
        widgets whose data is not contained in the saved state, are flagged as
        unassigned after the restore process. If the user shows an unassigned
        dock widget, a floating widget will be created to take up the dock
        widget.
        '''
        self.d.closed = True
        logger.debug('flag_as_unassigned %s -> setParent %s', self,
                     self.d.dock_manager)
        self.setParent(self.d.dock_manager)
        self.setVisible(False)
        self.set_dock_area(None)

        tab_widget = self.tab_widget()
        logger.debug('flag_as_unassigned %s -> setParent %s', tab_widget,
                     self)
        tab_widget.setParent(self)

    def emit_top_level_changed(self, floating: bool):
        '''
        Use this function to emit a top level changed event. Do never use emit
        top_level_changed(). Always use this function because it only emits a
        signal if the floating state has really changed

        Parameters
        ----------
        floating : bool
        '''
        if floating != self.d.is_floating_top_level:
            self.d.is_floating_top_level = floating
            self.top_level_changed.emit(self.d.is_floating_top_level)

    def set_closed_state(self, closed: bool):
        '''
        Internal function for modifying the closed state when restoring a saved
        docking state

        Parameters
        ----------
        closed : bool
        '''
        self.d.closed = closed

    def toggle_view_internal(self, open_: bool):
        '''
        Internal toggle view function that does not check if the widget already
        is in the given state

        Parameters
        ----------
        open_ : bool
        '''
        dock_container = self.dock_container()
        top_level_dock_widget_before = (dock_container.top_level_dock_widget()
                                        if dock_container else None)
        if open_:
            self.d.show_dock_widget()
        else:
            self.d.hide_dock_widget()

        self.d.closed = not open_
        self.d.toggle_view_action.blockSignals(True)
        self.d.toggle_view_action.setChecked(open_)
        self.d.toggle_view_action.blockSignals(False)
        if self.d.dock_area:
            self.d.dock_area.toggle_dock_widget_view(self, open_)

        if open_ and top_level_dock_widget_before:
            emit_top_level_event_for_widget(top_level_dock_widget_before, False)

        # Here we need to call the dockContainer() function again, because if
        # this dock widget was unassigned before the call to showDockWidget() then
        # it has a dock container now
        dock_container = self.dock_container()
        top_level_dock_widget_after = (dock_container.top_level_dock_widget()
                                       if dock_container
                                       else None)
        emit_top_level_event_for_widget(top_level_dock_widget_after, True)
        if dock_container is not None:
            floating_container = dock_container.floating_widget()
            if floating_container is not None:
                floating_container.update_window_title()

        if not open_:
            self.closed.emit()

        self.view_toggled.emit(open_)

    def minimumSizeHint(self) -> QSize:
        '''
        We return a fixed minimum size hint for all dock widgets

        Returns
        -------
        value : QSize
        '''
        return QSize(60, 40)

    def set_widget(self, widget: QWidget,
                   insert_mode: InsertMode = InsertMode.auto_scroll_area):
        '''
        Sets the widget for the dock widget to widget. The InsertMode defines
        how the widget is inserted into the dock widget. The content of a dock
        widget should be resizable do a very small size to prevent the dock
        widget from blocking the resizing. To ensure, that a dock widget can be
        resized very well, it is better to insert the content+ widget into a
        scroll area or to provide a widget that is already a scroll area or
        that contains a scroll area. If the InsertMode is AutoScrollArea, the
        DockWidget tries to automatically detect how to insert the given
        widget.

        If the widget is derived from QScrollArea (i.e. an QAbstractItemView),
        then the widget is inserted directly. If the given widget is not a
        scroll area, the widget will be inserted into a scroll area. To force
        insertion into a scroll area, you can also provide the InsertMode
        ForceScrollArea. To prevent insertion into a scroll area, you can
        provide the InsertMode ForceNoScrollArea

        Parameters
        ----------
        widget : QWidget
        insert_mode : InsertMode
        '''
        scroll_area = isinstance(widget, QScrollArea)
        if scroll_area or InsertMode.force_no_scroll_area == insert_mode:
            self.d.layout.addWidget(widget)
            if scroll_area:
                viewport = widget.viewport()
                if viewport is not None:
                    viewport.setProperty('dockWidgetContent', True)
        else:
            self.d.setup_scroll_area()
            self.d.scroll_area.setWidget(widget)

        self.d.widget = widget
        self.d.widget.setProperty("dockWidgetContent", True)

    def take_widget(self):
        '''
        Remove the widget from the dock, giving ownership back to the caller
        '''
        d = self.d
        d.scroll_area.takeWidget()
        widget = self.d.widget
        d.layout.removeWidget(widget)
        widget.setParent(None)
        return widget

    def widget(self) -> QWidget:
        '''
        Returns the widget for the dock widget. This function returns None if
        the widget has not been set.

        Returns
        -------
        value : QWidget
        '''
        return self.d.widget

    def tab_widget(self) -> 'DockWidgetTab':
        '''
        Returns the title bar widget of this dock widget

        Returns
        -------
        value : DockWidgetTab
        '''
        return self.d.tab_widget

    def set_features(self, features: DockWidgetFeature):
        '''
        Sets, whether the dock widget is movable, closable, and floatable.

        Parameters
        ----------
        features : DockWidgetFeature
        '''
        self.d.features = features

    def set_feature(self, flag: DockWidgetFeature, on: bool = True):
        '''
        Sets the feature flag for this dock widget if on is true; otherwise
        clears the flag.

        Parameters
        ----------
        flag : DockWidgetFeature
        on : bool
        '''
        if on:
            self.d.features |= flag
        else:
            self.d.features &= ~flag

    def features(self) -> DockWidgetFeature:
        '''
        This property holds whether the dock widget is movable, closable, and
        floatable. By default, this property is set to a combination of
        DockWidgetClosable, DockWidgetMovable and DockWidgetFloatable.

        Returns
        -------
        value : DockWidgetFeature
        '''
        return self.d.features

    def dock_manager(self) -> 'DockManager':
        '''
        Returns the dock manager that manages the dock widget or 0 if the
        widget has not been assigned to any dock manager yet

        Returns
        -------
        value : DockManager
        '''
        return self.d.dock_manager

    def dock_container(self) -> Optional['DockContainerWidget']:
        '''
        Returns the dock container widget this dock area widget belongs to or
        None if this dock widget has not been docked yet

        Returns
        -------
        value : DockContainerWidget
        '''
        return self.d.dock_area.dock_container() if self.d.dock_area else None

    def dock_area_widget(self) -> 'DockAreaWidget':
        '''
        Returns the dock area widget this dock widget belongs to or 0 if this
        dock widget has not been docked yet

        Returns
        -------
        value : DockAreaWidget
        '''
        return self.d.dock_area

    def is_floating(self) -> bool:
        '''
        This property holds whether the dock widget is floating. A dock widget
        is only floating, if it is the one and only widget inside of a floating
        container. If there are more than one dock widget in a floating
        container, the all dock widgets are docked and not floating.

        Returns
        -------
        value : bool
        '''
        if not self.is_in_floating_container():
            return False

        return self.dock_container().top_level_dock_widget() is self

    def is_in_floating_container(self) -> bool:
        '''
        This function returns true, if this dock widget is in a floating. The
        function returns true, if the dock widget is floating and it also
        returns true if it is docked inside of a floating container.

        Returns
        -------
        value : bool
        '''
        container = self.dock_container()
        return container and container.is_floating()

    def is_closed(self) -> bool:
        '''
        Returns true, if this dock widget is closed.

        Returns
        -------
        value : bool
        '''
        return self.d.closed

    def toggle_view_action(self) -> QAction:
        '''
        Returns a checkable action that can be used to show or close this dock
        widget. The action's text is set to the dock widget's window title.

        Returns
        -------
        value : QAction
        '''
        return self.d.toggle_view_action

    def set_toggle_view_action_mode(self, mode: ToggleViewActionMode):
        '''
        Configures the behavior of the toggle view action.

        Parameters
        ----------
        mode : ToggleViewActionMode
        '''
        is_action_mode = ToggleViewActionMode.toggle == mode
        self.d.toggle_view_action.setCheckable(is_action_mode)
        icon = QIcon() if is_action_mode else self.d.tab_widget.icon()
        if icon is not None:
            self.d.toggle_view_action.setIcon(icon)

    def set_icon(self, icon: QIcon):
        '''
        Sets the dock widget icon that is shown in tabs and in toggle view actions

        Parameters
        ----------
        icon : QIcon
        '''
        self.d.tab_widget.set_icon(icon)
        if not self.d.toggle_view_action.isCheckable():
            self.d.toggle_view_action.setIcon(icon)

    def icon(self) -> QIcon:
        '''
        Returns the icon that has been assigned to the dock widget

        Returns
        -------
        value : QIcon
        '''
        return self.d.tab_widget.icon()

    def tool_bar(self) -> QToolBar:
        '''
        If the WithToolBar layout flag is enabled, then this function returns
        the dock widget toolbar. If the flag is disabled, the function returns
        a nullptr. This function returns the dock widget top tool bar. If no
        toolbar is assigned, this function returns nullptr. To get a vaild
        toolbar you either need to create a default empty toolbar via
        createDefaultToolBar() function or you need to assign you custom
        toolbar via setToolBar().

        Returns
        -------
        value : QToolBar
        '''
        return self.d.tool_bar

    def create_default_tool_bar(self) -> QToolBar:
        '''
        If you would like to use the default top tool bar, then call this
        function to create the default tool bar. After this function the
        toolBar() function will return a valid toolBar() object.

        Returns
        -------
        value : QToolBar
        '''
        if not self.d.tool_bar:
            self.d.setup_tool_bar()

        return self.d.tool_bar

    def set_tool_bar(self, tool_bar: QToolBar):
        '''
        Assign a new tool bar that is shown above the content widget. The dock
        widget will become the owner of the tool bar and deletes it on
        destruction

        Parameters
        ----------
        tool_bar : QToolBar
        '''
        if self.d.tool_bar:
            self.d.tool_bar.deleteLater()
            self.d.tool_bar = None

        self.d.tool_bar = tool_bar
        self.d.layout.insertWidget(0, self.d.tool_bar)
        self.top_level_changed.connect(self.set_toolbar_floating_style)
        self.set_toolbar_floating_style(self.is_floating())

    def set_tool_bar_style(self, style: Qt.ToolButtonStyle, state: WidgetState):
        '''
        This function sets the tool button style for the given dock widget
        state. It is possible to switch the tool button style depending on the
        state. If a dock widget is floating, then here are more space and it is
        possible to select a style that requires more space like
        Qt.ToolButtonTextUnderIcon. For the docked state
        Qt.ToolButtonIconOnly might be better.

        Parameters
        ----------
        style : Qt.ToolButtonStyle
        state : WidgetState
        '''
        if WidgetState.floating == state:
            self.d.tool_bar_style_floating = style
        else:
            self.d.tool_bar_style_docked = style

        self.set_toolbar_floating_style(self.is_floating())

    def tool_bar_style(self, state: WidgetState) -> Qt.ToolButtonStyle:
        '''
        Returns the tool button style for the given docking state.

        Parameters
        ----------
        state : WidgetState

        Returns
        -------
        value : Qt.ToolButtonStyle
        '''
        return (self.d.tool_bar_style_floating
                if WidgetState.floating == state
                else self.d.tool_bar_style_docked
                )

    def set_tool_bar_icon_size(self, icon_size: QSize, state: WidgetState):
        '''
        This function sets the tool button icon size for the given state. If a
        dock widget is floating, there is more space an increasing the icon
        size is possible. For docked widgets, small icon sizes, eg. 16 x 16
        might be better.

        Parameters
        ----------
        icon_size : QSize
        state : WidgetState
        '''
        if WidgetState.floating == state:
            self.d.tool_bar_icon_size_floating = icon_size
        else:
            self.d.tool_bar_icon_size_docked = icon_size

        self.set_toolbar_floating_style(self.is_floating())

    def tool_bar_icon_size(self, state: WidgetState) -> QSize:
        '''
        Returns the icon size for a given docking state.

        Parameters
        ----------
        state : WidgetState

        Returns
        -------
        value : QSize
        '''
        return (self.d.tool_bar_icon_size_floating
                if WidgetState.floating == state
                else self.d.tool_bar_icon_size_docked)

    def set_tab_tool_tip(self, text: str):
        '''
        This is function sets text tooltip for title bar widget and tooltip for toggle view action

        Parameters
        ----------
        text : str
        '''
        if self.d.tab_widget:
            self.d.tab_widget.setToolTip(text)

        if self.d.toggle_view_action:
            self.d.toggle_view_action.setToolTip(text)

        if self.d.dock_area:
            # update tabs menu
            self.d.dock_area.mark_title_bar_menu_outdated()

    def event(self, e: QEvent) -> bool:
        '''
        Emits titleChanged signal if title change event occurs

        Parameters
        ----------
        e : QEvent

        Returns
        -------
        value : bool
        '''
        if e.type() == QEvent.WindowTitleChange:
            title = self.windowTitle()
            if self.d.tab_widget:
                self.d.tab_widget.setText(title)
            if self.d.toggle_view_action:
                self.d.toggle_view_action.setText(title)
            if self.d.dock_area:
                # update tabs menu
                self.d.dock_area.mark_title_bar_menu_outdated()

            self.title_changed.emit(title)

        return super().event(e)

    def toggle_view(self, open_: bool):
        '''
        This property controls whether the dock widget is open or closed. The
        toogleViewAction triggers this slot

        Parameters
        ----------
        open_ : bool
        '''
        # If the toggle view action mode is ActionModeShow, then Open is always
        # true if the sender is the toggle view action
        sender = self.sender()
        if sender is self.d.toggle_view_action and not self.d.toggle_view_action.isCheckable():
            open_ = True

        # If the dock widget state is different, then we really need to toggle
        # the state. If we are in the right state, then we simply make this
        # dock widget the current dock widget
        if self.d.closed != (not open_):
            self.toggle_view_internal(open_)
        elif open_ and self.d.dock_area:
            self.d.dock_area.set_current_dock_widget(self)

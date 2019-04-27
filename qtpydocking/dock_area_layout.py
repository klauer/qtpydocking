import logging
from typing import List

from qtpy.QtCore import QRect
from qtpy.QtWidgets import QBoxLayout, QWidget


logger = logging.getLogger(__name__)


class DockAreaLayout:
    _parent_layout: QBoxLayout
    _widgets: List[QWidget]
    _current_widget: QWidget
    _current_index: int

    def __init__(self, parent_layout: QBoxLayout):
        '''
        Creates an instance with the given parent layout

        Parameters
        ----------
        parent_layout : QBoxLayout
        '''
        self._parent_layout = parent_layout
        self._widgets = []
        self._current_index = -1
        self._current_widget = None

    def count(self) -> int:
        '''
        Returns the number of widgets in this layout

        Returns
        -------
        value : int
        '''
        return len(self._widgets)

    def insert_widget(self, index: int, widget: QWidget):
        '''
        Inserts the widget at the given index position into the internal widget
        list

        Parameters
        ----------
        index : int
        widget : QWidget
        '''
        logger.debug('%s setParent None', widget)
        widget.setParent(None)
        if index < 0:
            index = len(self._widgets)

        self._widgets.insert(index, widget)
        if self._current_index < 0:
            self.set_current_index(index)
        elif index <= self._current_index:
            self._current_index += 1

    def remove_widget(self, widget: QWidget):
        '''
        Removes the given widget from the lyout

        Parameters
        ----------
        widget : QWidget
        '''
        if self.current_widget() == widget:
            layout_item = self._parent_layout.takeAt(1)
            if layout_item:
                widget = layout_item.widget()
                logger.debug('%s setParent None', widget)
                widget.setParent(None)

            self._current_widget = None
            self._current_index = -1

        self._widgets.remove(widget)

    def current_widget(self) -> QWidget:
        '''
        Returns the current selected widget

        Returns
        -------
        value : QWidget
        '''
        return self._current_widget

    def set_current_index(self, index: int):
        '''
        Activates the widget with the give index.

        Parameters
        ----------
        index : int
        '''
        prev = self.current_widget()
        next_ = self.widget(index)
        if not next_ or (next_ is prev and not self._current_widget):
            return

        reenable_updates = False
        parent = self._parent_layout.parentWidget()
        if parent and parent.updatesEnabled():
            reenable_updates = True
            parent.setUpdatesEnabled(False)

        layout_item = self._parent_layout.takeAt(1)
        if layout_item:
            widget = layout_item.widget()
            logger.debug('%s setParent None', widget)
            widget.setParent(None)

        self._parent_layout.addWidget(next_)
        if prev:
            prev.hide()

        self._current_index = index
        self._current_widget = next_
        if reenable_updates:
            parent.setUpdatesEnabled(True)

    def current_index(self) -> int:
        '''
        Returns the index of the current active widget

        Returns
        -------
        value : int
        '''
        return self._current_index

    def is_empty(self) -> bool:
        '''
        Returns true if there are no widgets in the layout

        Returns
        -------
        value : bool
        '''
        return len(self._widgets) == 0

    def index_of(self, widget: QWidget) -> int:
        '''
        Returns the index of the given widget

        Parameters
        ----------
        widget : QWidget

        Returns
        -------
        value : int
        '''
        return self._widgets.index(widget)

    def widget(self, index: int) -> QWidget:
        '''
        Returns the widget for the given index

        Parameters
        ----------
        index : int

        Returns
        -------
        value : QWidget
        '''
        try:
            return self._widgets[index]
        except IndexError:
            return None

    def geometry(self) -> QRect:
        '''
        Returns the geometry of the current active widget

        Returns
        -------
        value : QRect
        '''
        if not self._widgets:
            return QRect()
        return self.current_widget().geometry()

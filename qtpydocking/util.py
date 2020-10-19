import sys
import functools

from typing import Optional, Any, Union, Type

from qtpy.QtCore import Qt, QEvent, QObject, QRegExp
from qtpy.QtGui import QPainter, QPixmap, QIcon
from qtpy.QtWidgets import QApplication, QStyle, QAbstractButton
from qtpy import QT_VERSION
# if needed, you can import specific boolean API variables from this module
# when implementing API code elsewhere
from qtpy import API, PYQT4, PYQT5, PYSIDE, PYSIDE2

from .dock_splitter import DockSplitter

DEBUG_LEVEL = 0
QT_VERSION_TUPLE = tuple(int(i) for i in QT_VERSION.split('.')[:3])
del QT_VERSION


LINUX = sys.platform.startswith('linux')


def emit_top_level_event_for_widget(widget: Optional['DockWidget'],
                                    floating: bool):
    '''
    Call this function to emit a topLevelChanged() signal and to update the
    dock area tool bar visibility

    Parameters
    ----------
    widget : DockWidget
        The top-level dock widget
    floating : bool
    '''
    if widget is None:
        return

    widget.dock_area_widget().update_title_bar_visibility()
    widget.emit_top_level_changed(floating)


def start_drag_distance() -> int:
    '''
    The distance the user needs to move the mouse with the left button hold
    down before a dock widget start floating

    Returns
    -------
    value : int
    '''
    return int(QApplication.startDragDistance() * 1.5)


def create_transparent_pixmap(source: QPixmap, opacity: float) -> QPixmap:
    '''
    Creates a semi transparent pixmap from the given pixmap Source. The Opacity
    parameter defines the opacity from completely transparent (0.0) to
    completely opaque (1.0)

    Parameters
    ----------
    source : QPixmap
    opacity : qreal

    Returns
    -------
    value : QPixmap
    '''
    transparent_pixmap = QPixmap(source.size())
    transparent_pixmap.fill(Qt.transparent)

    painter = QPainter(transparent_pixmap)
    painter.setOpacity(opacity)
    painter.drawPixmap(0, 0, source)
    return transparent_pixmap


def make_icon_pair(style, parent, standard_pixmap,
                   transparent_role=QIcon.Disabled, *,
                   transparency=0.25):
    '''
    Using a standard pixmap (e.g., close button), create two pixmaps and set
    parent icon
    '''
    icon = QIcon()
    normal_pixmap = style.standardPixmap(standard_pixmap, None, parent)
    icon.addPixmap(create_transparent_pixmap(normal_pixmap, transparency),
                   transparent_role)
    icon.addPixmap(normal_pixmap, QIcon.Normal)
    parent.setIcon(icon)
    return icon


def set_button_icon(style: QStyle, button: QAbstractButton,
                    standard_pixmap: QStyle.StandardPixmap) -> QIcon:
    '''
    Set a button icon

    Parameters
    ----------
    style : QStyle
    button : QAbstractButton
    standard_pixmap: QStyle.StandardPixmap

    Returns
    -------
    icon : QIcon
    '''
    if LINUX:
        icon = style.standardIcon(standard_pixmap)
        button.setIcon(icon)
        return icon

    return make_icon_pair(
        style, parent=button, standard_pixmap=standard_pixmap,
        transparent_role=QIcon.Disabled)


def hide_empty_parent_splitters(splitter: DockSplitter):
    '''
    This function walks the splitter tree upwards to hides all splitters that
    do not have visible content

    Parameters
    ----------
    splitter : DockSplitter
    '''
    while splitter and splitter.isVisible():
        if not splitter.has_visible_content():
            splitter.hide()

        splitter = find_parent(DockSplitter, splitter)


def find_parent(parent_type, widget):
    '''
    Searches for the parent widget of the given type.
    Returns the parent widget of the given widget or 0 if the widget is not
    child of any widget of type T

    It is not safe to use this function in in DockWidget because only
    the current dock widget has a parent. All dock widgets that are not the
    current dock widget in a dock area have no parent.
    '''
    parent_widget = widget.parentWidget()
    while parent_widget:
        if isinstance(parent_widget, parent_type):
            return parent_widget

        parent_widget = parent_widget.parentWidget()


def find_child(parent: Type[QObject], type: Type[QObject], name: str = '',
               options: Qt.FindChildOptions = Qt.FindChildrenRecursively) -> Optional[QObject]:
    '''
    Returns the child of this object that can be cast into type T and that is called name, or nullptr if there is no
    such object. Omitting the name argument causes all object names to be matched. The search is performed recursively,
    unless options specifies the option FindDirectChildrenOnly.

    If there is more than one child matching the search, the most direct ancestor is returned. If there are several
    direct ancestors, it is undefined which one will be returned. In that case, findChildren() should be used.

    WARNING: If you're using PySide, PySide2 or PyQt4, the options parameter will be discarded.
    '''

    if PYQT5:
        return parent.findChild(type, name, options)
    else:
        # every other API (PySide, PySide2, PyQt4) has no options parameter
        return parent.findChild(type, name)


def find_children(parent: Type[QObject], type: Type[QObject], name: Union[str, QRegExp] = '',
               options: Qt.FindChildOptions = Qt.FindChildrenRecursively) -> Optional[Any]:
    '''
    Returns all children of this object with the given name that can be cast to type T, or an empty list if there are no
    such objects. Omitting the name argument causes all object names to be matched. The search is performed recursively,
    unless options specifies the option FindDirectChildrenOnly.

    WARNING: If you're using PySide, PySide2 or PyQt4, the options parameter will be discarded.
    '''

    if PYQT5:
        return parent.findChildren(type, name, options)
    else:
        # every other API (PySide, PySide2, PyQt4) has no options parameter
        return parent.findChildren(type, name)


def event_filter_decorator(method):
    '''
    PySide2 exhibits some strange behavior where an eventFilter may get a
    'PySide2.QtWidgets.QWidgetItem` as the `event` argument. This wrapper
    effectively just makes those specific cases a no-operation.

    NOTE::
        This is considered a work-around until the source of the issue can be
        determined.
    '''
    if PYSIDE or PYSIDE2:
        @functools.wraps(method)
        def wrapped(self, obj: QObject, event: QEvent):
            if not isinstance(event, QEvent):
                return True
            return method(self, obj, event)
        return wrapped
    return method

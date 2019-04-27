from typing import Optional

from qtpy.QtCore import Qt
from qtpy.QtGui import QPainter, QPixmap
from qtpy.QtWidgets import QApplication
from qtpy import QT_VERSION

from .dock_splitter import DockSplitter


DEBUG_LEVEL = 0
QT_VERSION_TUPLE = tuple(int(i) for i in QT_VERSION.split('.')[:3])
del QT_VERSION


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

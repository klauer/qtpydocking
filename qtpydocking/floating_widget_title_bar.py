import logging
from typing import TYPE_CHECKING
import math

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QMouseEvent, QFontMetrics
from qtpy.QtWidgets import QBoxLayout, QSizePolicy, QStyle, QPushButton, QLabel, QWidget

from .enums import DragState
from .eliding_label import ElidingLabel
from .util import set_button_icon


if TYPE_CHECKING:
    from . import FloatingDockContainer


logger = logging.getLogger(__name__)


class FloatingWidgetTitleBarPrivate:
    public: 'FloatingWidgetTitleBar'
    icon_label: QLabel
    title_label: 'ElidingLabel'
    close_button: QPushButton
    floating_widget: 'FloatingDockContainer'
    drag_state: DragState

    def __init__(self, public: 'FloatingWidgetTitleBar'):
        '''
        Private data constructor

        Parameters
        ----------
        public : FloatingWidgetTitleBar
        '''
        self.public = public
        self.icon_label = None
        self.title_label = None
        self.close_button = None
        self.floating_widget = None
        self.drag_state = DragState.inactive

    def create_layout(self):
        '''
        Creates the complete layout including all controls
        '''
        self.title_label = ElidingLabel()
        self.title_label.set_elide_mode(Qt.ElideRight)
        self.title_label.setText("DockWidget->windowTitle()")
        self.title_label.setObjectName("floatingTitleLabel")
        self.title_label.setAlignment(Qt.AlignLeft)

        self.close_button = QPushButton()
        self.close_button.setObjectName("floatingTitleCloseButton")
        self.close_button.setFlat(True)

        # self.close_button.setAutoRaise(True)
        set_button_icon(self.public.style(), self.close_button, QStyle.SP_TitleBarCloseButton)

        self.close_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.close_button.setVisible(True)
        self.close_button.setFocusPolicy(Qt.NoFocus)
        self.close_button.clicked.connect(self.public.close_requested)

        fm = QFontMetrics(self.title_label.font())
        spacing = round(fm.height() / 4.0)

        # Fill the layout
        layout = QBoxLayout(QBoxLayout.LeftToRight)
        layout.setContentsMargins(6, 0, 0, 0)
        layout.setSpacing(0)
        self.public.setLayout(layout)
        layout.addWidget(self.title_label, 1)
        layout.addSpacing(spacing)
        layout.addWidget(self.close_button)
        layout.setAlignment(Qt.AlignCenter)
        self.title_label.setVisible(True)


class FloatingWidgetTitleBar(QWidget):
    close_requested = Signal()

    def __init__(self, parent: 'FloatingDockContainer'):
        super().__init__(parent)

        self.d = FloatingWidgetTitleBarPrivate(self)
        self.d.floating_widget = parent
        self.d.create_layout()

    def mousePressEvent(self, ev: QMouseEvent):
        if ev.button() == Qt.LeftButton:
            self.d.drag_state = DragState.floating_widget
            self.d.floating_widget.start_dragging(
                ev.pos(), self.d.floating_widget.size(), self)
            return

        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev: QMouseEvent):
        logger.debug('FloatingWidgetTitleBar.mouseReleaseEvent')
        self.d.drag_state = DragState.inactive
        super().mouseReleaseEvent(ev)

    def mouseMoveEvent(self, ev: QMouseEvent):
        if not (ev.buttons() & Qt.LeftButton) or self.d.drag_state == DragState.inactive:
            self.d.drag_state = DragState.inactive
        elif self.d.drag_state == DragState.floating_widget:
            # Move floating window
            self.d.floating_widget.move_floating()
        super().mouseMoveEvent(ev)

    def enable_close_button(self, enable: bool):
        self.d.close_button.setEnabled(enable)

    def set_title(self, text: str):
        self.d.title_label.setText(text)

from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtGui import QMouseEvent, QResizeEvent
from qtpy.QtWidgets import QLabel, QWidget

from .util import PYSIDE, PYSIDE2


class ElidingLabelPrivate:
    def __init__(self, public):
        '''
          init

        Parameters
        ----------
        public : CElidingLabel
        '''
        self.public = public
        self.elide_mode = Qt.ElideNone
        self.text = ''

    def elide_text(self, width: int):
        '''
        Elide text

        Parameters
        ----------
        width : int
        '''
        if self.is_mode_elide_none():
            return

        fm = self.public.fontMetrics()
        text = fm.elidedText(self.text, self.elide_mode,
                             width-self.public.margin()*2-self.public.indent())
        if text == "…":
            text = self.text[0]

        QLabel.setText(self.public, text)

    def is_mode_elide_none(self) -> bool:
        '''
        Convenience function to check if the

        Returns
        -------
        value : bool
        '''
        return Qt.ElideNone == self.elide_mode


class ElidingLabel(QLabel):
    # This signal is emitted if the user clicks on the label (i.e. pressed down
    # then released while the mouse cursor is inside the label)
    clicked = Signal()
    # This signal is emitted if the user does a double click on the label
    double_clicked = Signal()

    def __init__(self, text='', parent: QWidget = None,
                 flags: Qt.WindowFlags = Qt.Widget):
        '''
        init

        Parameters
        ----------
        parent : QWidget
        flags : Qt.WindowFlags
        '''
        if PYSIDE or PYSIDE2:
            kwarg = {'f': flags}
        else:
            kwarg = {'flags': flags}
        super().__init__(text, parent=parent, **kwarg)
        self.d = ElidingLabelPrivate(self)

        if text:
            self.d.text = text
            self.setToolTip(text)

    def mouseReleaseEvent(self, event: QMouseEvent):
        '''
        Mousereleaseevent

        Parameters
        ----------
        event : QMouseEvent
        '''
        super().mouseReleaseEvent(event)
        if event.button() != Qt.LeftButton:
            return

        self.clicked.emit()

    def resizeEvent(self, event: QResizeEvent):
        '''
        Resizeevent

        Parameters
        ----------
        event : QResizeEvent
        '''
        if not self.d.is_mode_elide_none():
            self.d.elide_text(event.size().width())

        super().resizeEvent(event)

    def mouseDoubleClickEvent(self, ev: QMouseEvent):
        '''
        Mousedoubleclickevent

        Parameters
        ----------
        ev : QMouseEvent
            Unused
        '''
        self.double_clicked.emit()
        super().mouseDoubleClickEvent(ev)

    def elide_mode(self) -> Qt.TextElideMode:
        '''
        Returns the text elide mode. The default mode is ElideNone

        Returns
        -------
        value : Qt.TextElideMode
        '''
        return self.d.elide_mode

    def set_elide_mode(self, mode: Qt.TextElideMode):
        '''
        Sets the text elide mode

        Parameters
        ----------
        mode : Qt.TextElideMode
        '''
        self.d.elide_mode = mode
        self.d.elide_text(self.size().width())

    def minimumSizeHint(self) -> QSize:
        '''
        Minimumsizehint

        Returns
        -------
        value : QSize
        '''
        if self.pixmap() is not None or self.d.is_mode_elide_none():
            return super().minimumSizeHint()

        fm = self.fontMetrics()
        return QSize(fm.width(self.d.text[:2]+"…"), fm.height())

    def sizeHint(self) -> QSize:
        '''
        Sizehint

        Returns
        -------
        value : QSize
        '''
        if self.pixmap() is not None or self.d.is_mode_elide_none():
            return super().sizeHint()

        fm = self.fontMetrics()
        return QSize(fm.width(self.d.text), super().sizeHint().height())

    def setText(self, text: str):
        '''
        Settext

        Parameters
        ----------
        text : str
        '''
        if self.d.is_mode_elide_none():
            super().setText(text)
        else:
            self.d.text = text
            self.setToolTip(text)
            self.d.elide_text(self.size().width())

    def text(self) -> str:
        '''
        Text

        Returns
        -------
        value : str
        '''
        return self.d.text

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QSplitter, QWidget


class DockSplitter(QSplitter):
    def __init__(self, orientation: Qt.Orientation = None,
                 parent: QWidget = None):
        '''
        init

        Parameters
        ----------
        parent : QWidget
        '''
        if orientation is not None:
            super().__init__(orientation, parent)
        else:
            super().__init__(parent)

        self.setProperty("ads-splitter", True)
        self.setChildrenCollapsible(False)

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.orientation()}>'

    def has_visible_content(self) -> bool:
        '''
        Returns true, if any of the internal widgets is visible

        Returns
        -------
        value : bool
        '''
        # TODO_UPSTREAM Cache or precalculate this to speed up

        for i in range(self.count()):
            if not self.widget(i).isHidden():
                return True

        return False

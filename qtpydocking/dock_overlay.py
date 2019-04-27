from typing import Dict

from qtpy.QtCore import (QEvent, QPoint, QPointF, QRect, Qt, QSizeF, QRectF,
                         QLineF)
from qtpy.QtGui import (QColor, QCursor, QHideEvent, QPaintEvent, QPainter,
                        QPalette, QShowEvent, QPixmap, QPolygonF)
from qtpy.QtWidgets import QFrame, QWidget, QLabel, QGridLayout


from .enums import OverlayMode, DockWidgetArea, IconColor, area_alignment
# from .dock_area_widget import DockAreaWidget
from .dock_container_widget import DockAreaWidget


class DockOverlayPrivate:
    public: 'DockOverlay'
    allowed_areas: DockWidgetArea
    cross: 'DockOverlayCross'
    target_widget: QWidget
    target_rect: QRect
    last_location: DockWidgetArea
    drop_preview_enabled: bool
    mode: OverlayMode
    drop_area_rect: QRect

    def __init__(self, public: 'DockOverlay'):
        '''
        Private data constructor

        Parameters
        ----------
        public : DockOverlay
        '''
        self.public = public
        self.allowed_areas = DockWidgetArea.invalid
        self.cross = None
        self.target_widget = None
        self.target_rect = None
        self.last_location = DockWidgetArea.invalid
        self.drop_preview_enabled = True
        self.mode = OverlayMode.dock_area
        self.drop_area_rect = None


class DockOverlay(QFrame):

    def __init__(self, parent: QWidget, mode: OverlayMode):
        '''
        Creates a dock overlay

        Parameters
        ----------
        parent : QWidget
        mode : OverlayMode
        '''
        super().__init__(parent)
        self.d = DockOverlayPrivate(self)
        self.d.mode = mode
        self.d.cross = DockOverlayCross(self)

        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setWindowOpacity(1)
        self.setWindowTitle("DockOverlay")
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.d.cross.setVisible(False)
        self.setVisible(False)

    def __repr__(self):
        return f'<DockOverlay mode={self.d.mode}>'

    def set_allowed_areas(self, areas: DockWidgetArea):
        '''
        Configures the areas that are allowed for docking

        Parameters
        ----------
        areas : DockWidgetArea
        '''
        if areas != self.d.allowed_areas:
            self.d.allowed_areas = areas
            self.d.cross.reset()

    def allowed_areas(self) -> DockWidgetArea:
        '''
        Returns flags with all allowed drop areas

        Returns
        -------
        value : DockWidgetArea
        '''
        return self.d.allowed_areas

    def drop_area_under_cursor(self) -> DockWidgetArea:
        '''
        Returns the drop area under the current cursor location

        Returns
        -------
        value : DockWidgetArea
        '''
        result = self.d.cross.cursor_location()
        if result != DockWidgetArea.invalid:
            return result

        dock_area = self.d.target_widget
        if isinstance(dock_area, DockAreaWidget):
            pos = dock_area.mapFromGlobal(QCursor.pos())
            if dock_area.title_bar_geometry().contains(pos):
                return DockWidgetArea.center

        return DockWidgetArea.invalid

    def show_overlay(self, target: QWidget) -> DockWidgetArea:
        '''
        Show the drop overlay for the given target widget

        Parameters
        ----------
        target : QWidget

        Returns
        -------
        value : DockWidgetArea
        '''
        if self.d.target_widget is target:
            # Hint: We could update geometry of overlay here.
            da = self.drop_area_under_cursor()
            if da != self.d.last_location:
                self.repaint()
                self.d.last_location = da

            return da

        self.d.target_widget = target
        self.d.target_rect = QRect()
        self.d.last_location = DockWidgetArea.invalid

        # Move it over the target.
        self.resize(target.size())
        top_left = target.mapToGlobal(target.rect().topLeft())
        self.move(top_left)
        self.show()
        self.d.cross.update_position()
        self.d.cross.update_overlay_icons()
        return self.drop_area_under_cursor()

    def hide_overlay(self):
        '''
        Hides the overlay
        '''
        self.hide()
        self.d.target_widget = None
        self.d.target_rect = QRect()
        self.d.last_location = DockWidgetArea.invalid

    def enable_drop_preview(self, enable: bool):
        '''
        Enables / disables the semi transparent overlay rectangle that
        represents the future area of the dropped widget

        Parameters
        ----------
        enable : bool
        '''
        self.d.drop_preview_enabled = enable
        self.update()

    def drop_overlay_rect(self) -> QRect:
        '''
        The drop overlay rectangle for the target area

        Returns
        -------
        value : QRect
        '''
        return self.d.drop_area_rect

    def event(self, e: QEvent) -> bool:
        '''
        Handle polish events

        Parameters
        ----------
        e : QEvent

        Returns
        -------
        value : bool
        '''
        result = super().event(e)
        if e.type() == QEvent.Polish:
            self.d.cross.setup_overlay_cross(self.d.mode)

        return result

    def paintEvent(self, e: QPaintEvent):
        '''
        Paintevent

        Parameters
        ----------
        e : QPaintEvent
            Unused
        '''
        #pylint: disable=unused-argument

        # Draw rect based on location
        if not self.d.drop_preview_enabled:
            self.d.drop_area_rect = QRect()
            return

        r = self.rect()
        da = self.drop_area_under_cursor()
        factor = (3
                  if OverlayMode.container == self.d.mode
                  else 2)

        if da == DockWidgetArea.top:
            r.setHeight(r.height()/factor)
        elif da == DockWidgetArea.right:
            r.setX(r.width() * (1 - 1./factor))
        elif da == DockWidgetArea.bottom:
            r.setY(r.height() * (1 - 1./factor))
        elif da == DockWidgetArea.left:
            r.setWidth(r.width()/factor)
        elif da == DockWidgetArea.center:
            r = self.rect()
        else:
            return

        painter = QPainter(self)
        color = self.palette().color(QPalette.Active, QPalette.Highlight)

        pen = painter.pen()
        pen.setColor(color.darker(120))
        pen.setStyle(Qt.SolidLine)
        pen.setWidth(1)
        pen.setCosmetic(True)
        painter.setPen(pen)
        color = color.lighter(130)
        color.setAlpha(64)
        painter.setBrush(color)
        painter.drawRect(r.adjusted(0, 0, -1, -1))
        self.d.drop_area_rect = r

    def showEvent(self, e: QShowEvent):
        '''
        Showevent

        Parameters
        ----------
        e : QShowEvent
        '''
        self.d.cross.show()
        super().showEvent(e)

    def hideEvent(self, e: QHideEvent):
        '''
        Hideevent

        Parameters
        ----------
        e : QHideEvent
        '''
        self.d.cross.hide()
        super().hideEvent(e)


class DockOverlayCrossPrivate:
    public: 'DockOverlayCross'
    mode: OverlayMode
    dock_overlay: DockOverlay
    drop_indicator_widgets: Dict[DockWidgetArea, QLabel]
    grid_layout: QGridLayout
    icon_colors: Dict[IconColor, QColor]
    update_required: bool
    last_device_pixel_ratio: float

    _area_grid_positions = {
        OverlayMode.dock_area: {
            DockWidgetArea.top: QPoint(1, 2),
            DockWidgetArea.right: QPoint(2, 3),
            DockWidgetArea.bottom: QPoint(3, 2),
            DockWidgetArea.left: QPoint(2, 1),
            DockWidgetArea.center: QPoint(2, 2),
        },
        OverlayMode.container: {
            DockWidgetArea.top: QPoint(0, 2),
            DockWidgetArea.right: QPoint(2, 4),
            DockWidgetArea.bottom: QPoint(4, 2),
            DockWidgetArea.left: QPoint(2, 0),
            DockWidgetArea.center: QPoint(2, 2),
        },
    }

    def __init__(self, public):
        '''
        Private data constructor

        Parameters
        ----------
        public : DockOverlayCross
        '''
        self.public = public
        self.mode = OverlayMode.dock_area
        self.dock_overlay = None
        self.drop_indicator_widgets = {}
        self.grid_layout = None
        self.icon_colors = {
            IconColor.frame_color: None,
            IconColor.window_background_color: None,
            IconColor.overlay_color: None,
            IconColor.arrow_color: None,
            IconColor.shadow_color: None,
        }

        self.update_required = False
        self.last_device_pixel_ratio = 0.1

    def area_grid_position(self, area: DockWidgetArea) -> QPoint:
        '''
        Returns

        Parameters
        ----------
        area : DockWidgetArea

        Returns
        -------
        value : QPoint
        '''
        return self._area_grid_positions[self.mode].get(area, QPoint())

    def default_icon_color(self, color_index: IconColor) -> QColor:
        '''
        Palette based default icon colors

        Parameters
        ----------
        color_index : IconColor

        Returns
        -------
        value : QColor
        '''
        pal = self.public.palette()
        if color_index == IconColor.frame_color:
            return pal.color(QPalette.Active, QPalette.Highlight)
        if color_index == IconColor.window_background_color:
            return pal.color(QPalette.Active, QPalette.Base)
        if color_index == IconColor.overlay_color:
            color = pal.color(QPalette.Active, QPalette.Highlight)
            color.setAlpha(64)
            return color
        if color_index == IconColor.arrow_color:
            return pal.color(QPalette.Active, QPalette.Base)
        if color_index == IconColor.shadow_color:
            return QColor(0, 0, 0, 64)
        return QColor()

    def icon_color(self, color_index: IconColor) -> QColor:
        '''
        Stylehseet based icon colors

        Parameters
        ----------
        color_index : IconColor

        Returns
        -------
        value : QColor
        '''
        color = self.icon_colors[color_index]
        if not color:
            color = self.default_icon_color(color_index)
            self.icon_colors[color_index] = color

        return color

    def create_drop_indicator_widget(self, area: DockWidgetArea, mode: OverlayMode) -> QLabel:
        '''
        Create drop indicator widget

        Parameters
        ----------
        area : DockWidgetArea
        mode : OverlayMode

        Returns
        -------
        value : QLabel
        '''
        l = QLabel()
        l.setObjectName("DockWidgetAreaLabel")

        metric = 3.0 * l.fontMetrics().height()
        size = QSizeF(metric, metric)
        l.setPixmap(self.create_high_dpi_drop_indicator_pixmap(size, area, mode))
        l.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        l.setAttribute(Qt.WA_TranslucentBackground)
        l.setProperty("dockWidgetArea", area)
        return l

    def update_drop_indicator_icon(self, label: QLabel):
        '''
        Update drop indicator icon

        Parameters
        ----------
        drop_indicator_widget : QLabel
        '''
        metric = 3.0 * label.fontMetrics().height()
        size = QSizeF(metric, metric)
        area = label.property("dockWidgetArea")
        label.setPixmap(
            self.create_high_dpi_drop_indicator_pixmap(size, area, self.mode)
        )

    def create_high_dpi_drop_indicator_pixmap(
            self, size: QSizeF, area: DockWidgetArea,
            mode: OverlayMode) -> QPixmap:
        '''
        Create high dpi drop indicator pixmap

        Parameters
        ----------
        size : QSizeF
        area : DockWidgetArea
        mode : OverlayMode

        Returns
        -------
        value : QPixmap
        '''
        border_color = self.icon_color(IconColor.frame_color)
        background_color = self.icon_color(IconColor.window_background_color)

        window = self.public.window()

        # QT version compatibility (TODO necessary for qtpy?)
        device_pixel_ratio = (window.devicePixelRatioF()
                              if hasattr(window, 'devicePixelRatioF')
                              else window.devicePixelRatio())

        pixmap_size = QSizeF(size * device_pixel_ratio)
        pm = QPixmap(pixmap_size.toSize())
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        pen = p.pen()
        shadow_rect = QRectF(pm.rect())

        base_rect = QRectF()
        base_rect.setSize(shadow_rect.size() * 0.7)
        base_rect.moveCenter(shadow_rect.center())

        # Fill
        shadow_color = self.icon_color(IconColor.shadow_color)
        if shadow_color.alpha() == 255:
            shadow_color.setAlpha(64)

        p.fillRect(shadow_rect, shadow_color)

        # Drop area rect.
        p.save()
        area_rect = QRectF()
        area_line = QLineF()
        non_area_rect = QRectF()

        if area == DockWidgetArea.top:
            area_rect = QRectF(base_rect.x(), base_rect.y(), base_rect.width(),
                               base_rect.height()*.5)
            non_area_rect = QRectF(base_rect.x(), shadow_rect.height()*.5,
                                   base_rect.width(), base_rect.height()*.5)
            area_line = QLineF(area_rect.bottomLeft(), area_rect.bottomRight())
        elif area == DockWidgetArea.right:
            area_rect = QRectF(shadow_rect.width()*.5, base_rect.y(),
                               base_rect.width()*.5, base_rect.height())
            non_area_rect = QRectF(base_rect.x(), base_rect.y(),
                                   base_rect.width()*.5, base_rect.height())
            area_line = QLineF(area_rect.topLeft(), area_rect.bottomLeft())
        elif area == DockWidgetArea.bottom:
            area_rect = QRectF(base_rect.x(), shadow_rect.height()*.5,
                               base_rect.width(), base_rect.height()*.5)
            non_area_rect = QRectF(base_rect.x(), base_rect.y(),
                                   base_rect.width(), base_rect.height()*.5)
            area_line = QLineF(area_rect.topLeft(), area_rect.topRight())
        elif area == DockWidgetArea.left:
            area_rect = QRectF(base_rect.x(), base_rect.y(),
                               base_rect.width()*.5, base_rect.height())
            non_area_rect = QRectF(shadow_rect.width()*.5, base_rect.y(),
                                   base_rect.width()*.5, base_rect.height())
            area_line = QLineF(area_rect.topRight(), area_rect.bottomRight())

        baseSize = base_rect.size()
        if (OverlayMode.container == mode
                and area != DockWidgetArea.center):
            base_rect = area_rect

        p.fillRect(base_rect, background_color)
        if area_rect.isValid():
            pen = p.pen()
            pen.setColor(border_color)
            Color = self.icon_color(IconColor.overlay_color)
            if Color.alpha() == 255:
                Color.setAlpha(64)

            p.setBrush(Color)
            p.setPen(Qt.NoPen)
            p.drawRect(area_rect)
            pen = p.pen()
            pen.setWidth(1)
            pen.setColor(border_color)
            pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.drawLine(area_line)

        p.restore()
        p.save()

        # Draw outer border
        pen = p.pen()
        pen.setColor(border_color)
        pen.setWidth(1)
        p.setBrush(Qt.NoBrush)
        p.setPen(pen)
        p.drawRect(base_rect)

        # draw window title bar
        p.setBrush(border_color)
        frame_rect = QRectF(base_rect.topLeft(),
                            QSizeF(base_rect.width(), baseSize.height()/10))
        p.drawRect(frame_rect)
        p.restore()

        # Draw arrow for outer container drop indicators
        if (OverlayMode.container == mode and
                area != DockWidgetArea.center):
            arrow_rect = QRectF()
            arrow_rect.setSize(baseSize)
            arrow_rect.setWidth(arrow_rect.width()/4.6)
            arrow_rect.setHeight(arrow_rect.height()/2)
            arrow_rect.moveCenter(QPointF(0, 0))

            arrow = QPolygonF()
            arrow.append(arrow_rect.topLeft())
            arrow.append(QPointF(arrow_rect.right(), arrow_rect.center().y()))
            arrow.append(arrow_rect.bottomLeft())

            p.setPen(Qt.NoPen)
            p.setBrush(self.icon_color(IconColor.arrow_color))
            p.setRenderHint(QPainter.Antialiasing, True)
            p.translate(non_area_rect.center().x(), non_area_rect.center().y())
            if area == DockWidgetArea.top:
                p.rotate(-90)
            elif area == DockWidgetArea.right:
                ...
            elif area == DockWidgetArea.bottom:
                p.rotate(90)
            elif area == DockWidgetArea.left:
                p.rotate(180)

            p.drawPolygon(arrow)

        pm.setDevicePixelRatio(device_pixel_ratio)
        return pm


class DockOverlayCross(QWidget):
    _all_areas = [
        DockWidgetArea.left,
        DockWidgetArea.right,
        DockWidgetArea.top,
        DockWidgetArea.bottom,
        DockWidgetArea.center,
    ]

    def __init__(self, overlay: DockOverlay):
        '''
        Creates an overlay cross for the given overlay

        Parameters
        ----------
        overlay : DockOverlay
        '''
        super().__init__(overlay.parentWidget())
        self.d = DockOverlayCrossPrivate(self)
        self.d.dock_overlay = overlay
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setWindowTitle("DockOverlayCross")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.d.grid_layout = QGridLayout()
        self.d.grid_layout.setSpacing(0)
        self.setLayout(self.d.grid_layout)

    def set_icon_frame_color(self, color: QColor):
        '''
        Set icon frame color

        Parameters
        ----------
        color : QColor
        '''
        self.set_icon_color(IconColor.frame_color, color)

    def set_icon_background_color(self, color: QColor):
        '''
        Set icon background color

        Parameters
        ----------
        color : QColor
        '''
        self.set_icon_color(IconColor.window_background_color, color)

    def set_icon_overlay_color(self, color: QColor):
        '''
        Set icon overlay color

        Parameters
        ----------
        color : QColor
        '''
        self.set_icon_color(IconColor.overlay_color, color)

    def set_icon_arrow_color(self, color: QColor):
        '''
        Set icon arrow color

        Parameters
        ----------
        color : QColor
        '''
        self.set_icon_color(IconColor.arrow_color, color)

    def set_icon_shadow_color(self, color: QColor):
        '''
        Set icon shadow color

        Parameters
        ----------
        color : QColor
        '''
        self.set_icon_color(IconColor.shadow_color, color)

    def set_icon_color(self, color_index: IconColor, color: QColor):
        '''
        Sets a certain icon color

        Parameters
        ----------
        color_index : IconColor
        color : QColor
        '''
        self.d.icon_colors[color_index] = color
        self.d.update_required = True

    def icon_color(self, color_index: IconColor) -> QColor:
        '''
        Returns the icon color given by ColorIndex

        Parameters
        ----------
        color_index : IconColor

        Returns
        -------
        value : QColor
        '''
        return self.d.icon_colors[color_index]

    def cursor_location(self) -> DockWidgetArea:
        '''
        Returns the dock widget area depending on the current cursor location.
        The function checks, if the mouse cursor is inside of any drop
        indicator widget and returns the corresponding DockWidgetArea.

        Returns
        -------
        value : DockWidgetArea
        '''
        pos = self.mapFromGlobal(QCursor.pos())
        allowed_areas = self.d.dock_overlay.allowed_areas()
        for area, widget in self.d.drop_indicator_widgets.items():
            if (area in allowed_areas and widget
                    and widget.isVisible()
                    and widget.geometry().contains(pos)):
                return area

        return DockWidgetArea.invalid

    def setup_overlay_cross(self, mode: OverlayMode):
        '''
        Sets up the overlay cross for the given overlay mode

        Parameters
        ----------
        mode : OverlayMode
        '''
        self.d.mode = mode
        area_widgets = {
            area: self.d.create_drop_indicator_widget(area, mode)
            for area in self._all_areas
        }

        self.d.last_device_pixel_ratio = (
            self.devicePixelRatioF()
            if hasattr(self, 'devicePixelRatioF')
            else self.devicePixelRatio())

        self.set_area_widgets(area_widgets)
        self.d.update_required = False

    def update_overlay_icons(self):
        '''
        Recreates the overlay icons.
        '''
        if self.windowHandle().devicePixelRatio() == self.d.last_device_pixel_ratio:
            return

        for widget in self.d.drop_indicator_widgets.values():
            self.d.update_drop_indicator_icon(widget)

        self.d.last_device_pixel_ratio = (
            self.devicePixelRatioF()
            if hasattr(self, 'devicePixelRatioF')
            else self.devicePixelRatio())

    def reset(self):
        '''
        Resets and updates the
        '''

        allowed_areas = self.d.dock_overlay.allowed_areas()

        # Update visibility of area widgets based on allowedAreas.
        for area in self._all_areas:
            pos = self.d.area_grid_position(area)
            item = self.d.grid_layout.itemAtPosition(pos.x(), pos.y())
            widget = item.widget()
            if item and widget is not None:
                widget.setVisible(area in allowed_areas)

    def update_position(self):
        '''
        Updates the current position
        '''
        self.resize(self.d.dock_overlay.size())
        top_left = self.d.dock_overlay.pos()
        offest = QPoint((self.width()-self.d.dock_overlay.width())/2,
                        (self.height()-self.d.dock_overlay.height())/2)
        cross_top_left = top_left-offest
        self.move(cross_top_left)

    def set_icon_colors(self, colors: str):
        '''
        A string with all icon colors to set. You can use this property to
        style the overly icon via CSS stylesheet file. The colors are set via a
        color identifier and a hex AARRGGBB value like in the example below.

        Parameters
        ----------
        colors : str
        '''
        string_to_color_type = {
            "Frame": IconColor.frame_color,
            "Background": IconColor.window_background_color,
            "Overlay": IconColor.overlay_color,
            "Arrow": IconColor.arrow_color,
            "Shadow": IconColor.shadow_color,
        }

        for color in colors.split(' '):
            try:
                name, value = color.replace(' ', '').split('=')
                color_type = string_to_color_type[name]
            except (KeyError, IndexError):
                continue

            self.d.icon_colors[color_type] = QColor(value)

        self.d.update_required = True

    def showEvent(self, event: QShowEvent):
        '''
        Showevent

        Parameters
        ----------
        e : QShowEvent
            Unused
        '''
        #pylint: disable=unused-argument

        if self.d.update_required:
            self.setup_overlay_cross(self.d.mode)

        self.update_position()

    def set_area_widgets(self, widgets: dict):
        '''
        Set area widgets

        Parameters
        ----------
        widgets : dict
            DockWidgetArea to QWidget
        '''
        # Delete old widgets.
        for area, widget in self.d.drop_indicator_widgets.items():
            self.d.grid_layout.removeWidget(widget)
            widget.destroyLater()

        self.d.drop_indicator_widgets.clear()

        # Insert new widgets into grid.
        self.d.drop_indicator_widgets = widgets
        for area, widget in self.d.drop_indicator_widgets.items():
            pos = self.d.area_grid_position(area)
            self.d.grid_layout.addWidget(widget, pos.x(), pos.y(),
                                         area_alignment[area])

        if OverlayMode.dock_area == self.d.mode:
            self.d.grid_layout.setContentsMargins(0, 0, 0, 0)
            stretch_values = [1, 0, 0, 0, 1]
        else:
            self.d.grid_layout.setContentsMargins(4, 4, 4, 4)
            stretch_values = [0, 1, 1, 1, 0]

        for i, stretch in zip(range(5), stretch_values):
            self.d.grid_layout.setRowStretch(i, stretch)
            self.d.grid_layout.setColumnStretch(i, stretch)

        self.reset()

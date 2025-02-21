from PyQt6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QMouseEvent
from PyQt6.QtWidgets import QWidget, QCheckBox


def take_closest(num, collection):
    return min(collection, key=lambda x: abs(x - num))


class SwitchCircle(QWidget):
    def __init__(self, parent, move_range: tuple, color, animation_curve, animation_duration):
        super().__init__(parent=parent)
        self.color = color
        self.move_range = move_range
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setEasingCurve(animation_curve)
        self.animation.setDuration(animation_duration)

    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.color))
        painter.drawEllipse(0, 0, 22, 22)
        painter.end()

    def set_color(self, value):
        self.color = value
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        self.animation.stop()
        self.oldX = event.globalPosition().x()
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        delta = event.globalPosition().x() - self.oldX
        self.new_x = delta + self.x()
        if self.new_x < self.move_range[0]:
            self.new_x += (self.move_range[0] - self.new_x)
        if self.new_x > self.move_range[1]:
            self.new_x -= (self.new_x - self.move_range[1])
        self.move(self.new_x, self.y())
        self.oldX = event.globalPosition().x()
        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        try:
            go_to = take_closest(self.new_x, self.move_range)
            if go_to == self.move_range[0]:
                self.animation.setStartValue(self.pos())
                self.animation.setEndValue(QPoint(go_to, self.y()))
                self.animation.start()
                self.parent().setChecked(False)
            elif go_to == self.move_range[1]:
                self.animation.setStartValue(self.pos())
                self.animation.setEndValue(QPoint(go_to, self.y()))
                self.animation.start()
                self.parent().setChecked(True)
        except AttributeError:
            pass
        return super().mouseReleaseEvent(event)


class SwitchControl(QCheckBox):
    def __init__(self, parent=None, bg_color="#777777", circle_color="#DDD", active_color="#aa00ff",
                 unchecked_color="darkgrey",
                 animation_curve=QEasingCurve.Type.OutBounce, animation_duration=300, checked: bool = False,
                 change_cursor=True, width=60, height=28):
        super().__init__(parent)
        self.setFixedSize(width, height)
        if change_cursor:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bg_color = bg_color
        self.circle_color = circle_color
        self.animation_curve = animation_curve
        self.animation_duration = animation_duration
        self.__circle = SwitchCircle(self, (3, self.width() - 26), self.circle_color, self.animation_curve,
                                     self.animation_duration)
        self.__circle_position = 3
        self.active_color = active_color
        self.unchecked_color = unchecked_color
        self.auto = False
        self.pos_on_press = None
        if checked:
            self.__circle.move(self.width() - 26, 3)
            self.setChecked(True)
        else:
            self.__circle.move(3, 3)
            self.setChecked(False)
        self.animation = QPropertyAnimation(self.__circle, b"pos")
        self.animation.setEasingCurve(animation_curve)
        self.animation.setDuration(animation_duration)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        enabled = self.isEnabled()
        if not self.isChecked():
            if enabled:
                painter.setBrush(QColor(self.unchecked_color))
            else:
                painter.setPen(Qt.PenStyle.SolidLine)
                painter.setPen(QColor("white"))
                painter.setBrush(QColor("black"))
            painter.drawRoundedRect(0, 0, self.width(), self.height(), self.height() / 2, self.height() / 2)
        else:
            if enabled:
                painter.setBrush(QColor(self.active_color))
            else:
                painter.setPen(Qt.PenStyle.SolidLine)
                painter.setPen(QColor("white"))
                painter.setBrush(QColor("black"))
            painter.drawRoundedRect(0, 0, self.width(), self.height(), self.height() / 2, self.height() / 2)

    def hitButton(self, pos):
        return self.contentsRect().contains(pos)

    def mousePressEvent(self, event: QMouseEvent):
        self.auto = True
        self.pos_on_press = event.globalPosition()
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.globalPosition() != self.pos_on_press:
            self.auto = False
        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.auto:
            self.auto = False
            self.start_animation(not self.isChecked())

    def start_animation(self, checked):
        self.animation.stop()
        self.animation.setStartValue(self.__circle.pos())
        if checked:
            self.animation.setEndValue(QPoint(self.width() - 26, self.__circle.y()))
            self.setChecked(True)
        else:
            self.animation.setEndValue(QPoint(3, self.__circle.y()))
            self.setChecked(False)
        self.animation.start()

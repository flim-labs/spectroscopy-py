import os
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget
from PyQt6.QtGui import QDesktopServices

current_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_path, ".."))


class LinkWidget(QWidget):
    """A custom widget that displays a clickable link with an optional icon and text."""

    def __init__(
        self,
        icon_filename=None,
        text=None,
        parent=None,
        icon_dimensions=25,
        icon_hover_dimensions=28,
        link="",
    ):
        """Initializes the LinkWidget.

        Args:
            icon_filename (str, optional): The file path to the icon. Defaults to None.
            text (str, optional): The text to display next to the icon. Defaults to None.
            parent (QWidget, optional): The parent widget. Defaults to None.
            icon_dimensions (int, optional): The default size of the icon. Defaults to 25.
            icon_hover_dimensions (int, optional): The size of the icon on hover. Defaults to 28.
            link (str, optional): The URL to open when the widget is clicked. Defaults to "".
        """
        super(LinkWidget, self).__init__(parent)

        layout = QHBoxLayout()

        if text:
            text_label = QLabel(text)
            layout.addWidget(text_label)
            text_label.mousePressEvent = self.open_link

        layout.addSpacing(10)

        self.link_label = QLabel()
        self.link = link

        if icon_filename:
            icon_path = icon_filename
            original_icon_pixmap = QPixmap(icon_path).scaled(
                icon_dimensions, icon_dimensions, Qt.AspectRatioMode.KeepAspectRatio
            )
            self.link_label.setPixmap(original_icon_pixmap)

        layout.addWidget(self.link_label)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setLayout(layout)

        self.link_label.mousePressEvent = self.open_link

    def open_link(self, event):
        """Opens the link in the default web browser.

        Args:
            event: The mouse press event.
        """
        QDesktopServices.openUrl(QUrl(self.link))

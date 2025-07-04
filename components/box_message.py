from PyQt6.QtWidgets import QMessageBox


class BoxMessage:
    """A utility class for displaying a QMessageBox."""

    @staticmethod
    def setup(title, msg, icon, style):
        """
        Creates and displays a customized QMessageBox.

        This static method configures and shows a modal message box
        with a specific title, message, icon, and stylesheet.

        Args:
            title (str): The title of the message box window.
            msg (str): The message text to be displayed.
            icon (QMessageBox.Icon): The icon to be shown in the message box.
            style (str): The CSS stylesheet to apply to the message box.
        """
        message_box = QMessageBox()
        message_box.setIcon(icon)
        message_box.setText(msg)
        message_box.setWindowTitle(title)
        message_box.setStyleSheet(style)
        message_box.exec()

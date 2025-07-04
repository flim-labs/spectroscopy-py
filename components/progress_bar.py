from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QProgressBar,
    QApplication,
    QHBoxLayout,
)
from PyQt6.QtCore import pyqtSignal
from typing import Literal, Optional

from utils.gui_styles import GUIStyles


class ProgressBar(QWidget):
    """A custom progress bar widget that includes a label and a progress bar.

    This widget can be configured to be either determinate or indeterminate,
    and can be laid out horizontally or vertically. It emits a 'complete'
    signal when the progress reaches 100%.

    Attributes:
        complete (pyqtSignal): Signal emitted when the progress is complete.
    """
    
    complete = pyqtSignal() 

    def __init__(
        self,
        label_text: str = None,
        color: str = "#DA1212",
        visible: bool = True,
        enabled: bool = True,
        stylesheet: str  = None,
        layout_type: Literal["horizontal", "vertical"] = "vertical",
        spacing: int = 10,
        progress_bar_height: int  = 15,
        progress_bar_width: int  = None,
        indeterminate: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initializes the ProgressBar widget.

        Args:
            label_text (str, optional): The text to display on the label. Defaults to None.
            color (str, optional): The color of the progress bar. Defaults to "#DA1212".
            visible (bool, optional): Whether the widget is initially visible. Defaults to True.
            enabled (bool, optional): Whether the widget is initially enabled. Defaults to True.
            stylesheet (str, optional): A custom stylesheet for the widget. Defaults to None.
            layout_type (Literal["horizontal", "vertical"], optional): The layout orientation. Defaults to "vertical".
            spacing (int, optional): The spacing between the label and the progress bar. Defaults to 10.
            progress_bar_height (int, optional): The height of the progress bar. Defaults to 15.
            progress_bar_width (int, optional): The width of the progress bar. Defaults to None.
            indeterminate (bool, optional): Whether the progress bar is indeterminate. Defaults to False.
            parent (Optional[QWidget], optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.color = color
        self.indeterminate = indeterminate

        # Initialize layout based on layout_type
        if layout_type == "horizontal":
            self.layout = QHBoxLayout()
        else:
            self.layout = QVBoxLayout()
            
        self.label_layout = QHBoxLayout()
        self.label_layout.setContentsMargins(0,0,0,0)   
        self.label_layout.setSpacing(0) 

        self.layout.setContentsMargins(0, 0, 0, 0)
       
        # Set the spacing between widgets in the layout if label_text is provided
        if label_text is not None:
            self.layout.setSpacing(spacing)

        # Create and configure the label if label_text is provided
        if label_text is not None:
            self.label = QLabel(label_text)

        # Create and configure the progress bar
        self.progress_bar = QProgressBar()
        if progress_bar_height is not None:
            self.progress_bar.setFixedHeight(progress_bar_height)
        if progress_bar_width is not None:
            self.progress_bar.setFixedWidth(progress_bar_width)

        # Add widgets to the layout
        if layout_type == "horizontal":
            self.layout.addWidget(self.progress_bar)

        if label_text is not None:
            self.label_layout.addWidget(self.label)
    
        if layout_type == "horizontal":
            if label_text is not None:
                self.layout.addLayout(self.label_layout)
        else:
            if label_text is not None:
                self.layout.addLayout(self.label_layout)
            self.layout.addWidget(self.progress_bar)

        self.setLayout(self.layout)
        self.set_visible(visible)
        self.set_enabled(enabled)
        self.set_style(stylesheet)

        # Set the progress bar to indeterminate mode if specified
        if indeterminate:
            self.set_indeterminate_mode(True)

    def set_indeterminate_mode(self, state: bool) -> None:
        """Sets the progress bar to indeterminate or determinate mode.

        Args:
            state (bool): If True, sets to indeterminate mode. If False, sets to determinate mode.
        """
        if state:
            self.progress_bar.setRange(0, 0)  # Indeterminate mode
        else:
            self.progress_bar.setRange(0, 100)  # Switch back to determinate mode
        QApplication.processEvents()

    def update_progress(
        self, current_value: int, total_value: int, label_text: Optional[str] = None
    ) -> None:
        """Updates the progress of the determinate progress bar.

        Args:
            current_value (int): The current progress value.
            total_value (int): The total value representing 100% progress.
            label_text (Optional[str], optional): Text to update the label with. Defaults to None.
        """
        if not self.indeterminate:
            progress_value = (current_value / float(total_value)) * 100
            self.progress_bar.setValue(int(progress_value))
            if label_text:
                self.label.setText(label_text)
            
            # Emit signal if progress is complete
            if progress_value >= 100:
                self.complete.emit()            
            QApplication.processEvents()

    def clear_progress(self) -> None:
        """Resets the progress bar to 0 and clears the label text."""
        if not self.indeterminate:
            self.progress_bar.setValue(0)
            self.label.clear()
            QApplication.processEvents()
        
    def get_value(self) -> int:
        """Gets the current value of the progress bar.

        Returns:
            int: The current progress value (0-100).
        """
        return self.progress_bar.value()        

    def set_visible(self, visible: bool) -> None:
        """Sets the visibility of the widget.

        Args:
            visible (bool): If True, the widget is shown; otherwise, it is hidden.
        """
        self.setVisible(visible)
        QApplication.processEvents()

    def set_enabled(self, state: bool) -> None:
        """Sets the enabled state of the progress bar.

        Args:
            state (bool): If True, the progress bar is enabled; otherwise, it is disabled.
        """
        self.progress_bar.setEnabled(state)
        QApplication.processEvents()

    def set_style(self, stylesheet: str) -> None:
        """Applies a stylesheet to the widget.

        If no stylesheet is provided, a default style is applied.

        Args:
            stylesheet (str): The stylesheet to apply.
        """
        self.setStyleSheet(
            stylesheet
            if stylesheet is not None
            else GUIStyles.progress_bar_style(self.color)
        )
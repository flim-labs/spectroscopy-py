from PyQt6.QtWidgets import QWidget, QFrame, QSizePolicy, QVBoxLayout, QLayout


def draw_layout_separator(line_width=1, color="#282828", vertical_space=10, type="horizontal"):
    """Creates a visual separator widget (a line with spacing).

    Args:
        line_width (int, optional): The thickness of the separator line. Defaults to 1.
        color (str, optional): The color of the line. Defaults to "#282828".
        vertical_space (int, optional): The space above the line. Defaults to 10.
        type (str, optional): The orientation of the line ('horizontal' or 'vertical'). Defaults to "horizontal".

    Returns:
        QWidget: A container widget holding the separator.
    """
    spacer_widget = QWidget()
    spacer_widget.setFixedSize(1, vertical_space)

    separator = QFrame()
    if type == 'horizontal':
        separator.setFrameShape(QFrame.Shape.HLine)
    else: 
        separator.setFrameShape(QFrame.Shape.VLine)    
    separator.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
    separator.setLineWidth(line_width)
    separator.setStyleSheet(f"QFrame{{color: {color};}}")

    layout = QVBoxLayout()
    layout.setSpacing(0)
    layout.setContentsMargins(0,0,0,0)
    layout.addWidget(spacer_widget)
    layout.addWidget(separator)

    container_widget = QWidget()
    container_widget.setLayout(layout)

    return container_widget


def hide_layout(layout):
    """Recursively hides all widgets within a given layout.

    Args:
        layout (QLayout): The layout to hide.
    """
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.widget():
            item.widget().hide()
        elif item.layout():
            hide_layout(item.layout())

def show_layout(layout):
    """Recursively shows all widgets within a given layout.

    Args:
        layout (QLayout): The layout to show.
    """
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.widget():
            item.widget().show()
        elif item.layout():
            show_layout(item.layout())
            
            
def clear_layout(layout):
    """Recursively removes and deletes all items (widgets and sub-layouts) from a layout.

    Args:
        layout (QLayout): The layout to clear.
    """
    if layout is not None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                sub_layout = item.layout()
                if sub_layout is not None:
                    clear_layout(sub_layout)
        layout.deleteLater()
        
        
def clear_layout_widgets(layout):
    """Removes and deletes all widgets directly contained within a layout.

    This does not recurse into sub-layouts.

    Args:
        layout (QLayout): The layout whose widgets are to be cleared.
    """
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()       
            
            
 
def clear_layout_tree(layout: QLayout): 
    """Recursively removes and deletes all items (widgets and sub-layouts) from a layout tree.

    Args:
        self: The object instance (note: this function might be intended as a method).
        layout (QLayout): The layout to clear.
    """
    if layout is not None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                clear_layout_tree(item.layout())
        del layout

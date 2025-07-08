from PyQt6.QtCore import QPropertyAnimation, QPoint, QEasingCurve, QAbstractAnimation



class VibrantAnimation:
    """
    A class to create a vibrant animation effect on a widget.

    This animation moves the widget horizontally with a bounce effect and can
    change its style (e.g., color) when the animation starts and stops.
    """
    def __init__(self, widget, start_color="", stop_color="", bg_color="", margin_top=""):
        """
        Initializes the VibrantAnimation.

        Args:
            widget (QWidget): The widget to animate.
            start_color (str, optional): The text color when the animation starts. Defaults to "".
            stop_color (str, optional): The text color when the animation stops. Defaults to "".
            bg_color (str, optional): The background color of the widget. Defaults to "".
            margin_top (str, optional): The top margin for the widget's style. Defaults to "".
        """
        self.widget = widget
        self.start_color = start_color
        self.stop_color = stop_color
        self.bg_color = bg_color
        self.margin_top = margin_top
        self.animation = QPropertyAnimation(widget, b"pos")
        self.animation.setEasingCurve(QEasingCurve.Type.OutBounce)
        self.animation.setLoopCount(-1)
        self.original_pos = widget.pos()  
        
    def start(self, amplitude=10, duration=50):
        """
        Starts the animation.

        If the animation is already running, this method does nothing.

        Args:
            amplitude (int, optional): The horizontal movement amplitude. Defaults to 10.
            duration (int, optional): The duration of one animation cycle in milliseconds. Defaults to 50.
        """
        if self.animation.state() == QAbstractAnimation.State.Running:
            return
        self.original_pos = self.widget.pos()
        self.widget.setStyleSheet(        
                    f"QLabel {{ color : {self.start_color}; font-size: 42px; font-weight: bold; background-color: {self.bg_color}; padding: 8px 8px 0 8px;}}"
                )         
        self.animation.setDuration(duration)
        self.animation.setStartValue(self.original_pos)
        self.animation.setKeyValueAt(0.5, QPoint(self.original_pos.x() + amplitude, self.original_pos.y()))
        self.animation.setEndValue(self.original_pos)
        self.animation.start()

    def stop(self):
        """
        Stops the animation and resets the widget to its original position and style.

        If the animation is not running, this method does nothing.
        """
        if self.animation.state() == QAbstractAnimation.State.Running:
            self.widget.setStyleSheet(        
                        f"QLabel {{ color : {self.stop_color}; font-size: 42px; font-weight: bold; background-color: {self.bg_color}; padding: 8px 8px 0 8px;}}"
                    )              
            self.animation.stop()
            self.widget.move(self.original_pos)

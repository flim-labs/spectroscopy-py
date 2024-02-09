# run .ui file ui/test-main.ui

import sys
from PyQt6 import QtWidgets, uic


class App(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(App, self).__init__(parent)
        self.ui = uic.loadUi('ui/test-main.ui', self)
        self.ui.show()

    def robeeeeeeee(self, io: int):
        print(io)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = App()
    sys.exit(app.exec())

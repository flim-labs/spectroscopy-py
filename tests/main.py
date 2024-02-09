import sys
import time
from PyQt6 import QtWidgets, QtCore
import numpy as np
import pyqtgraph as pg
from matplotlib import colormaps

print(list(colormaps))


class App(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(App, self).__init__(parent)

        self.mainbox = QtWidgets.QWidget()
        self.setCentralWidget(self.mainbox)
        self.mainbox.setLayout(QtWidgets.QVBoxLayout())

        self.canvas = pg.GraphicsLayoutWidget()

        self.mainbox.layout().addWidget(self.canvas)

        self.label = QtWidgets.QLabel()
        self.mainbox.layout().addWidget(self.label)

        self.view = self.canvas.addViewBox()
        self.view.setAspectLocked(True)
        self.view.setRange(QtCore.QRectF(0, 0, 100, 50))

        self.img = pg.ImageItem(border='w')
        self.img.setLookupTable(pg.colormap.getFromMatplotlib('viridis').getLookupTable())
        self.view.addItem(self.img)

        self.canvas.nextRow()
        #  line plot
        self.otherplot = self.canvas.addPlot()
        self.h2 = self.otherplot.plot(pen='y')

        self.x = np.linspace(0, 50., num=200)
        self.X, self.Y = np.meshgrid(self.x, self.x)

        self.counter = 0
        self.fps = 0.
        self.lastupdate = time.time()

        self._update()

    def _update(self):
        self.data = np.sin(self.X / 3. + self.counter / 9.) * np.cos(self.Y / 3. + self.counter / 9.)
        self.ydata = np.sin(self.x / 5. + self.counter / 9.)

        self.img.setImage(self.data)
        self.h2.setData(self.ydata)

        now = time.time()
        dt = (now - self.lastupdate)
        if dt <= 0:
            dt = 0.000000000001
        fps2 = 1.0 / dt
        self.lastupdate = now
        self.fps = self.fps * 0.9 + fps2 * 0.1
        tx = 'Mean Frame Rate:  {fps:.3f} FPS'.format(fps=self.fps)
        self.label.setText(tx)
        QtCore.QTimer.singleShot(1, self._update)
        self.counter += 1


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    thisapp = App()
    thisapp.show()
    sys.exit(app.exec())

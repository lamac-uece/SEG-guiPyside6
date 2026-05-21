import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.figure import Figure
from skimage.segmentation import mark_boundaries
from PySide6 import QtCore
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton

from src.models.segmentation_state import SegmentationState
from src.services.image_processing import compute_superpixels
from src.views.toolbar import MplToolbar


class QPaletteButton(QPushButton):
    def __init__(self, color: str):
        super().__init__()
        self.setFixedSize(QtCore.QSize(24, 24))
        self.color = color
        self.setStyleSheet(f"background-color: {color};")


class PlotSuperPixelMask(QWidget):
    """Painel que exibe a máscara pintada com os superpixels sobrepostos."""

    def __init__(self, state: SegmentationState, mouse_event_cb, parent=None):
        super().__init__(parent)
        self._state = state
        self._mouse_event_cb = mouse_event_cb

        self.view    = FigureCanvas(Figure())
        self.axes    = self.view.figure.subplots()
        self.axes.set_title("Máscara/SuperPixel")
        self.toolbar = MplToolbar(self.view, self, plot=1, state=state)
        self.im      = ""

        self.view.mpl_connect('button_press_event', self._on_click)

        layout = QVBoxLayout(self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.view)

    def _on_click(self, event):
        self._state.current_plot = 0
        self._mouse_event_cb(event, 1)

    def UpdateView(self):
        s = self._state
        if not s.masks_empty:
            data = (
                mark_boundaries(s.mask3d, s.segments_global * s.selected_hu)
                if s.show_superpixel and not np.array_equal(s.segments_global, [])
                else s.mask3d
            )
            if self.im == "":
                self.axes.clear()
                self.axes.set_title("Máscara/SuperPixel")
                self.im = self.axes.imshow(data)
            else:
                self.im.set_clim([0, 255])
                self.im.set_data(data)
            self.view.draw()
        else:
            if self.im == "":
                self.axes.clear()
                self.axes.set_title("Máscara/SuperPixel")
                self.im = self.axes.imshow(s.dicom_image_array, cmap='gray')
            else:
                self.im.set_data(s.dicom_image_array)
                self.im.set_clim([
                    s.dicom_image_array.min(),
                    s.dicom_image_array.max()
                ])
            self.view.draw()

    def showSavedMask(self):
        self.axes.clear()
        self.axes.set_title("Máscara/SuperPixel")
        self.im = self.axes.imshow(self._state.mask3d)
        self.view.draw()

    def ClearView(self):
        self.axes.clear()
        self.axes.set_title("Máscara/SuperPixel")

    def SuperPixel(self):
        s = self._state
        s.segments_global = compute_superpixels(
            s.dicom_image_array,
            n_segments=s.num_segments,
            sigma=s.sigma_slic,
            compactness=s.compactness,
            start_label=1,
            max_num_iter=s.max_num_iter,
            min_size_factor=s.min_size_factor,
            max_size_factor=s.max_size_factor,
        )
        self.axes.clear()
        self.axes.set_title("Máscara/SuperPixel")
        if not np.array_equal(s.mask3d, []):
            self.im = self.axes.imshow(
                mark_boundaries(s.mask3d, s.segments_global * s.selected_hu)
            )
        else:
            self.im = self.axes.imshow(
                mark_boundaries(s.dicom_image_array / 255,
                                s.segments_global * s.selected_hu),
                cmap='gray'
            )
        self.view.draw()
        s.superpixel_auth = True
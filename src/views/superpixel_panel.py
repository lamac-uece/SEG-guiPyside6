import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.figure import Figure
from skimage.color import gray2rgb
from skimage.segmentation import mark_boundaries
from skimage.util import img_as_float
from PySide6 import QtCore
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton

from src.models.segmentation_state import SegmentationState
from src.models.mesh_config import UNSAFE_MESH_MODES
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

    def __init__(self, state: SegmentationState, mouse_event_cb,
                 on_back_paint=None, on_save_mask=None, parent=None):
        super().__init__(parent)
        self._state          = state
        self._mouse_event_cb = mouse_event_cb

        self.view    = FigureCanvas(Figure())
        self.axes    = self.view.figure.subplots()
        self.axes.set_title("Mask/SuperPixel")
        self.toolbar = MplToolbar(
            self.view, self, plot=1, state=state,
            on_back_paint=on_back_paint,
            on_save_mask=on_save_mask,
        )
        self.im = ""

        self.view.mpl_connect('button_press_event', self._on_click)

        layout = QVBoxLayout(self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.view)

    def _on_click(self, event):
        self._state.current_plot = 0
        self._mouse_event_cb(event, 1)

    def _masked_segments(self, s):
        """Aplica máscara de HU sobre labels SLIC, devolvendo array int32"""
        if np.array_equal(s.selected_hu, []):
            return s.segments_global.astype(np.int32)
        return (s.segments_global * s.selected_hu.astype(np.int32)).astype(np.int32)

    def _boundary_overlay(self, image, segments):
        """Desenha a malha do SuperPixel sobre `image`, aplicando a cor,
        a grossura (mode) e a opacidade configuradas em Options.
        """
        s    = self._state
        mode = s.mesh_mode if s.mesh_mode not in UNSAFE_MESH_MODES else "outer"

        marked = mark_boundaries(
            image, segments,
            color=s.mesh_color,
            mode=mode,
        )

        opacity = min(max(float(s.mesh_opacity), 0.0), 1.0)
        if opacity >= 1.0:
            result = marked
        else:
            base = img_as_float(image)
            if base.ndim == 2:
                base = gray2rgb(base)
            result = base * (1 - opacity) + marked * opacity
            
        return np.clip(result, 0.0, 1.0)

    def UpdateView(self):
        s = self._state
        if not s.masks_empty:
            data = (
                self._boundary_overlay(s.mask3d, self._masked_segments(s))
                if s.show_superpixel and not np.array_equal(s.segments_global, [])
                else s.mask3d
            )
            if self.im == "":
                self.axes.clear()
                self.axes.set_title("Mask/SuperPixel")
                self.im = self.axes.imshow(data)
            else:
                self.im.set_clim([0, 255])
                self.im.set_data(data)
            self.view.draw()
        else:
            if self.im == "":
                self.axes.clear()
                self.axes.set_title("Mask/SuperPixel")
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
        self.axes.set_title("Mask/SuperPixel")
        self.im = self.axes.imshow(self._state.mask3d)
        self.view.draw()

    def ClearView(self):
        self.axes.clear()
        self.axes.set_title("Mask/SuperPixel")

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
        self.axes.set_title("Mask/SuperPixel")
        masked = self._masked_segments(s)
        if not np.array_equal(s.mask3d, []):
            self.im = self.axes.imshow(
                self._boundary_overlay(s.mask3d, masked)
            )
        else:
            self.im = self.axes.imshow(
                self._boundary_overlay(s.dicom_image_array / 255,
                                       masked),
                cmap='gray'
            )
        self.view.draw()
        s.superpixel_auth = True
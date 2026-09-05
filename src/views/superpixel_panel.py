import numpy as np
import pydicom
from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.figure import Figure
from skimage.color import gray2rgb
from skimage.segmentation import mark_boundaries
from skimage.util import img_as_float
from PySide6 import QtCore
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton

from src.models.segmentation_state import SegmentationState
from src.models.mesh_config import UNSAFE_MESH_MODES
from src.services.dicom_service import dicom2array
from src.services.image_processing import (
    apply_clahe,
    compute_superpixels,
    select_RoI,
    removeSkinAndObjects,
)
from src.utils.image_utils import ConvertToUint8
from src.views.theme import apply_canvas_theme
from src.views.toolbar import MplToolbar


class QPaletteButton(QPushButton):
    def __init__(self, color: str):
        super().__init__()
        self.setFixedSize(QtCore.QSize(24, 24))
        self.color = color
        self.setStyleSheet(f"background-color: {color};")


class PlotSuperPixelMask(QWidget):
    """Canvas central único.

    Exibe a vista de trabalho (máscara pintada + malha do SLIC) e também,
    quando em modo de comparação, a imagem de referência pré-processada em
    tons de cinza (sem pintura e sem malha). Também concentra as operações de
    pré-processamento (CLаHE, remoção de pele/objetos, restauração), que hoje
    atualizam apenas o estado em memória — a renderização é sempre do canvas
    central.
    """

    def __init__(self, state: SegmentationState, mouse_event_cb,
                 on_back_paint=None, on_save_mask=None, parent=None):
        super().__init__(parent)
        self._state          = state
        self._mouse_event_cb = mouse_event_cb
        self._in_comparison  = False

        self.view    = FigureCanvas(Figure())
        apply_canvas_theme(self.view.figure)
        self.axes    = self.view.figure.subplots()
        self.axes.set_title("Mask/SuperPixel")
        apply_canvas_theme(self.view.figure)
        self.toolbar = MplToolbar(
            self.view, self, plot=1, state=state,
        )
        self.im = ""

        self.view.mpl_connect('button_press_event', self._on_click)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.view)

    # ── modo de comparação ──────────────────────────────────────────────────
    @property
    def comparison_active(self) -> bool:
        return self._in_comparison

    def show_comparison(self, active: bool) -> None:
        self._in_comparison = bool(active)
        self.UpdateView()

    # ── interação ───────────────────────────────────────────────────────────
    def _on_click(self, event):
        self._state.current_plot = 0
        self._mouse_event_cb(event, 1)

    # ── desenho auxiliar ────────────────────────────────────────────────────
    def _redraw_theme(self):
        apply_canvas_theme(self.view.figure)

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

    def _show_reference(self):
        """Exibe o DICOM pré-processado atual em tons de cinza (imagem de
        conferência), sem pintura e sem malha."""
        s = self._state
        if np.array_equal(s.dicom_image_array, []):
            if self.im != "":
                self.axes.clear()
                self.axes.set_title("Comparação — sem imagem")
                self._redraw_theme()
                self.view.draw()
            return
        if self.im == "":
            self.axes.clear()
            self.axes.set_title("Comparação — pré-processado (somente leitura)")
            self.im = self.axes.imshow(s.dicom_image_array, cmap='gray')
        else:
            self.im.set_data(s.dicom_image_array)
            self.im.set_cmap('gray')
            self.im.set_clim([s.dicom_image_array.min(),
                              s.dicom_image_array.max()])
        self._redraw_theme()
        self.view.draw()

    def UpdateView(self):
        if self._in_comparison:
            self._show_reference()
            return
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
            self._redraw_theme()
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
            self._redraw_theme()
            self.view.draw()

    def showSavedMask(self):
        if self._in_comparison:
            self._show_reference()
            return
        self.axes.clear()
        self.axes.set_title("Mask/SuperPixel")
        self.im = self.axes.imshow(self._state.mask3d)
        self._redraw_theme()
        self.view.draw()

    def ClearView(self):
        self.axes.clear()
        self.axes.set_title("Mask/SuperPixel")
        self._redraw_theme()

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
        self._redraw_theme()
        self.view.draw()
        s.superpixel_auth = True

    # ── pré-processamento (atualizam apenas estado; canvas central desenha) ─
    def _set_base(self, base_img):
        """Registra a imagem base (pré-CLAHE) e o resultado atual em memória."""
        s = self._state
        s.base_image_array = base_img
        s.dicom_image_array = base_img
        s.superpixel_auth = False

    def on_change(self):
        """Exibe a imagem atual após conversão para uint8."""
        s = self._state
        base_img = ConvertToUint8(s.dicom_image_array)
        self._set_base(base_img)

    def EnableClahe(self):
        """Aplica CLAHE uma única vez sobre a imagem base."""
        s = self._state
        if np.array_equal(s.base_image_array, []):
            return
        s.dicom_image_array = apply_clahe(
            s.base_image_array,
            clip_limit=s.clip_limit,
            nbins=s.nbins,
        )
        s.superpixel_auth = False

    def DisableClahe(self):
        """Volta à imagem base (escala de cinza original/pré-processada)."""
        s = self._state
        if np.array_equal(s.base_image_array, []):
            return
        s.dicom_image_array = s.base_image_array
        s.superpixel_auth = False

    def ResetDicom(self):
        """Relê o DICOM do disco e atualiza a base sem processamento."""
        s = self._state
        if s.file_name_global:
            self._set_base(
                ConvertToUint8(
                    dicom2array(pydicom.dcmread(s.file_name_global, force=True))
                )
            )

    def DeleteObjects(self):
        """Remove objetos externos (mesa, lençol) sem remover pele."""
        s = self._state
        if s.file_name_global:
            self._set_base(
                ConvertToUint8(
                    select_RoI(
                        dicom2array(pydicom.dcmread(s.file_name_global, force=True))
                    )
                )
            )

    def DeleteSkinAndObjects(self):
        """Remove pele e objetos externos."""
        s = self._state
        if s.file_name_global:
            self._set_base(
                ConvertToUint8(
                    removeSkinAndObjects(
                        dicom2array(pydicom.dcmread(s.file_name_global, force=True)),
                        s.multiplicator,
                    )
                )
            )

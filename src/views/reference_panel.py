import pydicom
from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtWidgets import QWidget, QVBoxLayout

from src.models.segmentation_state import SegmentationState
from src.services.dicom_service import dicom2array
from src.services.image_processing import apply_clahe, select_RoI, removeSkinAndObjects
from src.utils.image_utils import ConvertToUint8
from src.views.toolbar import MplToolbar


class PlotWidgetModify(QWidget):
    """Painel de conferência que exibe a imagem DICOM processada."""

    def __init__(self, state: SegmentationState, mouse_event_cb,
                 on_back_paint=None, on_save_mask=None, parent=None):
        super().__init__(parent)
        self._state          = state
        self._mouse_event_cb = mouse_event_cb

        self.view    = FigureCanvas(Figure())
        self.axes    = self.view.figure.subplots()
        self.axes.set_title("Imagem Conferência")
        self.toolbar = MplToolbar(
            self.view, self, plot=2, state=state,
            on_back_paint=on_back_paint,
            on_save_mask=on_save_mask,
        )

        self.view.mpl_connect('button_press_event', self._on_click)

        layout = QVBoxLayout(self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.view)

    def _on_click(self, event):
        self._state.current_plot = 1
        self._mouse_event_cb(event, 2)

    def HistMethodClahe(self):
        s = self._state
        if not s.file_name_global:
            return
        s.dicom_image_array = apply_clahe(
            s.dicom_image_array,
            clip_limit=s.clip_limit,
            nbins=s.nbins,
        )
        s.superpixel_auth = False
        self.axes.clear()
        self.axes.set_title("Imagem Conferência")
        self.axes.imshow(s.dicom_image_array, cmap='gray')
        self.view.draw()

    def on_change(self):
        """Exibe a imagem atual após conversão para uint8."""
        s = self._state
        s.dicom_image_array = ConvertToUint8(s.dicom_image_array)
        s.superpixel_auth   = False
        self.axes.clear()
        self.axes.set_title("Imagem Conferência")
        if s.file_name_global:
            self.axes.imshow(s.dicom_image_array, cmap='gray')
            self.view.draw()

    def ResetDicom(self):
        """Relê o DICOM do disco e exibe sem processamento."""
        s = self._state
        if s.file_name_global:
            s.dicom_image_array = ConvertToUint8(
                dicom2array(pydicom.dcmread(s.file_name_global, force=True))
            )
        s.superpixel_auth = False
        self.axes.set_title("Imagem Conferência")
        self.axes.imshow(s.dicom_image_array, cmap='gray')
        self.view.draw()

    def DeleteObjects(self):
        """Remove objetos externos (mesa, lençol) sem remover pele."""
        s = self._state
        if s.file_name_global:
            s.dicom_image_array = ConvertToUint8(
                select_RoI(
                    dicom2array(pydicom.dcmread(s.file_name_global, force=True))
                )
            )
        s.superpixel_auth = False
        self.axes.set_title("Imagem Conferência")
        self.axes.imshow(s.dicom_image_array, cmap='gray')
        self.view.draw()

    def DeleteSkinAndObjects(self):
        """Remove pele e objetos externos."""
        s = self._state
        if s.file_name_global:
            s.dicom_image_array = ConvertToUint8(
                removeSkinAndObjects(
                    dicom2array(pydicom.dcmread(s.file_name_global, force=True)),
                    s.multiplicator,
                )
            )
        s.superpixel_auth = False
        self.axes.set_title("Imagem Conferência")
        self.axes.imshow(s.dicom_image_array, cmap='gray')
        self.view.draw()
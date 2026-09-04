import copy
from os import path
import os

import numpy as np
import pydicom
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFileDialog, QMessageBox

from src.models.segmentation_state import SegmentationState
from src.models.tissue_config import (
    FALLBACK_COLOR,
    default_tissue_color,
    dictTissues,
)
from src.services.dicom_service import dicom2array, get_dicom_identifier
from src.services.image_processing import select_RoI
from src.services.mask_io import load_mask, save_mask
from src.services.undo_manager import UndoStack
from src.views.dialogs import CustomDialog
from src.utils.image_utils import ConvertToUint8, tissue_segmentation

_LOCAL_DIR = "local"

class MainController:
    def __init__(self, state: SegmentationState):
        self._state      = state
        self._view       = None
        self._undo_stack = UndoStack()

    def set_view(self, view) -> None:
        self._view = view

    def open_file(self, file_path: str) -> None:
        s = self._state
        self._undo_stack.clear()
        s.superpixel_auth  = False
        s.file_name        = file_path
        s.file_name_global = file_path
        if file_path.split(".")[-1] == "csv":
            self._open_csv(file_path)
        else:
            self._open_dicom(file_path)

    def _open_csv(self, file_path: str) -> None:
        s = self._state
        s.csv_flag = True
        s.segmented_mask, s.informacoes, s.area, s.csv_source_id = load_mask(file_path)
        s.dicom_image_array = []
        s.base_image_array  = []
        self.set_clahe_enabled(False)
        s.masks_empty    = False
        s.current_tissue = 1
        if s.informacoes["tissue"]:
            self._sync_tissue_ui(
                self._tissue_name(s.informacoes["tissue"][0])
            )
        self.recovery_mask3d()
        self._view.plotwidget_modify.axes.clear()
        self._view.plotwidget_modify.axes.set_title("Imagem Conferência")
        self._view.plotwidget_modify.view.draw()

    def _open_dicom(self, file_path: str) -> None:
        s   = self._state
        dcm = pydicom.dcmread(file_path, force=True)
        s.dicom_image_array = dicom2array(dcm)
        if s.dicom_image_array is None:
            QMessageBox.critical(self._view, "Erro",
                                 "Não foi possível ler o arquivo DICOM.")
            return
        s.dicom_source_id = get_dicom_identifier(dcm, file_path)
        roi           = select_RoI(s.dicom_image_array)
        s.muscle_hu   = tissue_segmentation(roi, "muscle")
        s.fat_hu      = tissue_segmentation(roi, "fat")
        s.selected_hu = np.ones(s.dicom_image_array.shape)
        s.area = int(np.count_nonzero(ConvertToUint8(roi)))
        s.dicom_image_array = ConvertToUint8(s.dicom_image_array)
        self.set_clahe_enabled(False)
        self._view.plotwidget_modify.on_change()
        self._ask_initial_tissue()
        s.csv_flag = False

    def _ask_initial_tissue(self) -> None:
        s  = self._state
        v  = self._view
        ok = 0
        if s.csv_flag and s.csv_source_id and s.csv_source_id == s.dicom_source_id:
            ok = CustomDialog().show()
        if ok:
            s.current_tissue = 1
            if s.informacoes["tissue"]:
                self._sync_tissue_ui(
                    self._tissue_name(s.informacoes["tissue"][0])
                )
            s.segments_global = []
            self._update_selected_hu()
            self.recovery_mask3d()
            s.masks_empty = False
        else:
            s.mask3d          = []
            v.plotsuperpixelmask.im = ""
            s.masks_empty     = True
            s.current_tissue  = 0
            s.segmented_mask  = []
            s.segments_global = []
            s.informacoes     = {"colors": [], "identifier": [], "tissue": []}
            v.current_tissue_label.setText("None")
            self._update_selected_hu()
            v.plotsuperpixelmask.UpdateView()
            v.sync_tissue_palette()

    def recovery_mask3d(self) -> None:
        s = self._state
        s.masks  = np.zeros_like(s.segmented_mask, dtype="bool")
        s.mask3d = np.zeros(
            (s.segmented_mask.shape[0], s.segmented_mask.shape[1], 3),
            dtype="uint8"
        )
        if not np.array_equal(s.dicom_image_array, []):
            s.mask3d[:, :, 0] = s.dicom_image_array
            s.mask3d[:, :, 1] = s.dicom_image_array
            s.mask3d[:, :, 2] = s.dicom_image_array
        for i in range(len(s.informacoes["tissue"])):
            s.masks = np.zeros_like(s.segmented_mask, dtype="bool")
            s.masks[s.segmented_mask == s.informacoes["identifier"][i]] = 1
            c = s.informacoes["colors"][i]
            s.mask3d[:, :, 0] = c[0] * s.masks + s.mask3d[:, :, 0] * (~s.masks).astype("uint8")
            s.mask3d[:, :, 1] = c[1] * s.masks + s.mask3d[:, :, 1] * (~s.masks).astype("uint8")
            s.mask3d[:, :, 2] = c[2] * s.masks + s.mask3d[:, :, 2] * (~s.masks).astype("uint8")
        self._view.plotsuperpixelmask.showSavedMask()

    def reset_mask3d(self) -> None:
        s = self._state
        if np.array_equal(s.dicom_image_array, []):
            return
        self._undo_stack.clear()
        s.mask3d = np.zeros(
            (s.dicom_image_array.shape[0], s.dicom_image_array.shape[1], 3),
            dtype="uint8"
        )
        s.mask3d[:, :, 0] = s.dicom_image_array
        s.mask3d[:, :, 1] = s.dicom_image_array
        s.mask3d[:, :, 2] = s.dicom_image_array
        s.masks_empty = False
        self._view.plotsuperpixelmask.UpdateView()

    def paint_superpixel(self, x: float, y: float,
                         segments, plot: int) -> None:
        s = self._state
        if segments[int(y)][int(x)] == 0:
            return
        if s.current_tissue == 0:
            return
        if np.array_equal(s.segmented_mask, []):
            s.segmented_mask = np.zeros_like(s.dicom_image_array, dtype="uint8")
        if s.masks_empty:
            s.mask3d = np.zeros(
                (s.dicom_image_array.shape[0], s.dicom_image_array.shape[1], 3),
                dtype="uint8"
            )
            s.mask3d[:, :, 0] = s.dicom_image_array
            s.mask3d[:, :, 1] = s.dicom_image_array
            s.mask3d[:, :, 2] = s.dicom_image_array
            s.masks_empty = False

        s.masks    = np.zeros_like(s.dicom_image_array, dtype="bool")
        segment_id = segments[int(y)][int(x)]
        prev_id    = s.segmented_mask[int(y)][int(x)]

        # registra no UndoStack antes de modificar
        self._undo_stack.push(s.mask3d, segment_id, prev_id)

        if (plot == 1 and s.undo == 1) or (plot == 2 and s.undo == 2) or s.undo == 3:
            s.masks = np.ones_like(s.dicom_image_array, dtype="bool")
            s.segmented_mask[segments == segment_id] = 0
            s.masks[segments == segment_id] = 0
            s.mask3d[:, :, 0] = (s.dicom_image_array * (~s.masks).astype("uint8")
                                  + s.mask3d[:, :, 0] * s.masks.astype("uint8"))
            s.mask3d[:, :, 1] = (s.dicom_image_array * (~s.masks).astype("uint8")
                                  + s.mask3d[:, :, 1] * s.masks.astype("uint8"))
            s.mask3d[:, :, 2] = (s.dicom_image_array * (~s.masks).astype("uint8")
                                  + s.mask3d[:, :, 2] * s.masks.astype("uint8"))
        else:
            hu_mask = np.ones_like(s.dicom_image_array, dtype=bool)
            if s.radio_density_check_enabled:
                tissue = s.informacoes["tissue"][s.current_tissue - 1]
                if tissue in [1, 2, 3]:
                    hu_mask = hu_mask * s.fat_hu
                elif tissue in [5]:
                    hu_mask = hu_mask * s.muscle_hu
            s.segmented_mask[(hu_mask * segments) == segment_id] = s.current_tissue
            s.masks[(hu_mask * segments) == segment_id] = 1
            color = s.informacoes["colors"][s.current_tissue - 1]
            s.mask3d[:, :, 0] = color[0] * s.masks + s.mask3d[:, :, 0] * (~s.masks).astype("uint8")
            s.mask3d[:, :, 1] = color[1] * s.masks + s.mask3d[:, :, 1] * (~s.masks).astype("uint8")
            s.mask3d[:, :, 2] = color[2] * s.masks + s.mask3d[:, :, 2] * (~s.masks).astype("uint8")

        self._view.plotsuperpixelmask.UpdateView()

    def back_paint(self) -> None:
        """Desfaz a última pintura usando UndoStack."""
        s     = self._state
        entry = self._undo_stack.pop()
        if entry is None:
            return
        s.mask3d = entry.mask3d_snapshot
        s.segmented_mask[
            s.segments_global == entry.segment_id
        ] = entry.previous_identifier
        if np.array_equal(s.segments_global, []) and not np.array_equal(s.mask3d, []):
            self._view.plotsuperpixelmask.showSavedMask()
        else:
            self._view.plotsuperpixelmask.UpdateView()

    def save_mask_action(self) -> None:
        """Abre diálogo de salvamento e persiste a máscara."""
        s = self._state
        if np.array_equal(s.segmented_mask, []):
            return
        from PySide6.QtCore import QDir
        base_dir       = s.save_dir if (s.save_dir and path.exists(s.save_dir)) \
                         else QDir.currentPath()
        suggested_name = path.basename(s.file_name_global).split(".")[0] + ".csv"
        file_path, _   = QFileDialog.getSaveFileName(
            self._view, "Save File",
            path.join(base_dir, suggested_name),
            filter="csv(*.csv)"
        )
        if file_path:
            save_mask(file_path, s.segmented_mask, s.informacoes, s.area,
                      s.dicom_source_id)

    def save_mask_file(self, file_path: str) -> None:
        """Salva diretamente num caminho conhecido (uso programático)."""
        s = self._state
        if not np.array_equal(s.segmented_mask, []):
            save_mask(file_path, s.segmented_mask, s.informacoes, s.area,
                      s.dicom_source_id)

    def toggle_clahe(self, enabled: bool) -> None:
        """Liga/desliga o CLAHE como opção On/Off aplicada uma única vez."""
        s = self._state
        if np.array_equal(s.dicom_image_array, []):
            self._view.sync_clahe_action(False)
            return
        self._reset_toggle()
        s.clahe_enabled = enabled
        if s.masks_empty:
            self._view.plotsuperpixelmask.im = ""
        if enabled:
            self._view.plotwidget_modify.EnableClahe()
        else:
            self._view.plotwidget_modify.DisableClahe()
        self._refresh_superpixel_panel()
        self._view.sync_clahe_action(enabled)

    def reapply_clahe(self) -> None:
        """Reaplica o CLAHE sobre a base após mudança de parâmetros."""
        s = self._state
        if not s.clahe_enabled or np.array_equal(s.dicom_image_array, []):
            return
        self._reset_toggle()
        if s.masks_empty:
            self._view.plotsuperpixelmask.im = ""
        self._view.plotwidget_modify.EnableClahe()
        self._refresh_superpixel_panel()

    def set_clahe_enabled(self, enabled: bool) -> None:
        """Seta o flag e mantém o menu sincronizado."""
        self._state.clahe_enabled = enabled
        if self._view is not None:
            self._view.sync_clahe_action(enabled)

    def apply_superpixel(self) -> None:
        self._reset_toggle()
        if not np.array_equal(self._state.dicom_image_array, []):
            self._view.plotsuperpixelmask.SuperPixel()
            self._state.toggle_available = True
            self._view.sync_tissue_palette()

    def remove_objects(self) -> None:
        s = self._state
        self.set_clahe_enabled(False)
        self._reset_toggle()
        if np.array_equal(s.dicom_image_array, []):
            return
        if s.masks_empty:
            self._view.plotsuperpixelmask.im = ""
        self._view.plotwidget_modify.DeleteObjects()
        self._refresh_superpixel_panel()

    def remove_skin(self) -> None:
        s = self._state
        self.set_clahe_enabled(False)
        self._reset_toggle()
        if np.array_equal(s.dicom_image_array, []):
            return
        if s.masks_empty:
            self._view.plotsuperpixelmask.im = ""
        self._view.plotwidget_modify.DeleteSkinAndObjects()
        self._refresh_superpixel_panel()

    def restore_original(self) -> None:
        s = self._state
        self.set_clahe_enabled(False)
        self._reset_toggle()
        if not s.file_name_global or s.file_name_global.split(".")[-1] == "csv":
            return
        self._view.plotwidget_modify.ResetDicom()
        if s.masks_empty:
            self._view.plotsuperpixelmask.im = ""
        self._refresh_superpixel_panel()

    def select_tissue(self, tissue_name: str) -> None:
        """Ativa um tecido para pintura, escolhido pela paleta da interface.

        Se o tecido ainda não tiver entrada em `informacoes`, ela é criada
        com a cor padrão (ou fallback). Só tem efeito com o SuperPixel ativo.
        """
        s = self._state
        if not s.superpixel_auth:
            return
        idx = self._tissue_entry_index(tissue_name)
        if idx is None:
            size = len(s.informacoes["colors"])
            color = default_tissue_color(tissue_name)
            if color is None:
                color = FALLBACK_COLOR
            s.informacoes["colors"].append(color)
            s.informacoes["identifier"].append(size + 1)
            s.informacoes["tissue"].append(dictTissues[tissue_name])
            idx = size
        s.current_tissue = idx + 1
        self._sync_tissue_ui(tissue_name)
        self._update_selected_hu()
        self._view.plotsuperpixelmask.UpdateView()

    def on_color_selected(self, color: QColor) -> None:
        """Troca a cor do tecido atualmente selecionado na paleta."""
        s = self._state
        v = self._view
        if s.current_tissue == 0:
            QMessageBox.information(
                v, "Nenhum tecido selecionado",
                "Escolha um tecido na faixa superior antes de trocar a cor."
            )
            return
        selected = np.array([color.red(), color.green(), color.blue()])
        idx = s.current_tissue - 1
        s.informacoes["colors"][idx] = selected
        name = self._tissue_name(s.informacoes["tissue"][idx])
        if name is not None:
            v.current_tissue_label.setText(name)
        v.set_color(color)
        if not np.array_equal(s.mask3d, []):
            s.masks = np.zeros_like(s.dicom_image_array, dtype="bool")
            s.masks[s.segmented_mask == s.current_tissue] = 1
            ct = s.current_tissue - 1
            s.mask3d[:, :, 0] = (s.informacoes["colors"][ct][0] * s.masks
                                 + s.mask3d[:, :, 0] * (~s.masks).astype("uint8"))
            s.mask3d[:, :, 1] = (s.informacoes["colors"][ct][1] * s.masks
                                 + s.mask3d[:, :, 1] * (~s.masks).astype("uint8"))
            s.mask3d[:, :, 2] = (s.informacoes["colors"][ct][2] * s.masks
                                 + s.mask3d[:, :, 2] * (~s.masks).astype("uint8"))
        self._update_selected_hu()
        v.plotsuperpixelmask.UpdateView()
        v.sync_tissue_palette()

    def _tissue_entry_index(self, tissue_name: str):
        """Índice da entrada do tecido em informacoes, ou None se não existir."""
        try:
            return self._state.informacoes["tissue"].index(
                dictTissues[tissue_name]
            )
        except ValueError:
            return None

    def _tissue_name(self, tissue_id: int):
        """Nome amigável do tecido a partir do id usado em informacoes."""
        for key, val in dictTissues.items():
            if val == tissue_id:
                return key
        return None

    def _sync_tissue_ui(self, tissue_name: str) -> None:
        """Atualiza label, ícone de cor e paleta conforme o tecido ativo."""
        s = self._state
        v = self._view
        if tissue_name is not None:
            v.current_tissue_label.setText(tissue_name)
        if 0 < s.current_tissue <= len(s.informacoes["colors"]):
            color = s.informacoes["colors"][s.current_tissue - 1]
            v.set_color(QColor(int(color[0]), int(color[1]), int(color[2])))
        v.sync_tissue_palette()

    def load_dirs(self) -> None:
        s = self._state
        img_path  = path.join(_LOCAL_DIR, "defaultImageDir.txt")
        mask_path = path.join(_LOCAL_DIR, "defaultMaskDir.txt")
        if path.exists(img_path):
            with open(img_path) as f:
                s.open_dir = f.readline().strip()
        if path.exists(mask_path):
            with open(mask_path) as f:
                s.save_dir = f.readline().strip()

    def set_default_open_dir(self, parent_widget) -> None:
        d = QFileDialog.getExistingDirectory(parent_widget)
        if d:
            self._state.open_dir = d
            os.makedirs(_LOCAL_DIR, exist_ok=True)
            with open(path.join(_LOCAL_DIR, "defaultImageDir.txt"), "w") as f:
                f.write(d)

    def set_default_save_dir(self, parent_widget) -> None:
        d = QFileDialog.getExistingDirectory(parent_widget)
        if d:
            self._state.save_dir = d
            os.makedirs(_LOCAL_DIR, exist_ok=True)
            with open(path.join(_LOCAL_DIR, "defaultMaskDir.txt"), "w") as f:
                f.write(d)

    def _reset_toggle(self) -> None:
        s = self._state
        s.show_superpixel  = True
        s.superpixel_auth  = False
        s.toggle_available = False

    def _refresh_superpixel_panel(self) -> None:
        s = self._state
        v = self._view
        if np.array_equal(s.segments_global, []) and not np.array_equal(s.mask3d, []):
            self.recovery_mask3d()
            v.plotsuperpixelmask.showSavedMask()
        elif not np.array_equal(s.mask3d, []):
            self.recovery_mask3d()
            v.plotsuperpixelmask.showSavedMask()
        else:
            v.plotsuperpixelmask.UpdateView()
        v.sync_tissue_palette()

    def _update_selected_hu(self) -> None:
        s = self._state
        if s.current_tissue == 0 or not s.informacoes["tissue"]:
            shape = getattr(s.dicom_image_array, "shape", (0, 0))
            s.selected_hu = np.ones(shape, dtype=bool)
            return
        tissue = s.informacoes["tissue"][s.current_tissue - 1]
        if tissue in [1, 2, 3]:
            s.selected_hu = s.fat_hu
        elif tissue in [5]:
            s.selected_hu = s.muscle_hu
        else:
            s.selected_hu = np.ones(s.dicom_image_array.shape, dtype=bool)
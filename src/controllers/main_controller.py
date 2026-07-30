import copy
from os import path
import os

import numpy as np
import pydicom
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from src.models.segmentation_state import SegmentationState
from src.models.tissue_config import dictTissues
from src.services.dicom_service import dicom2array, get_dicom_identifier
from src.services.image_processing import select_RoI
from src.services.mask_io import load_mask, save_mask
from src.services.ml_segmentation import (
    MLSegmentationError, available_tissues, predict_mask,
)
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
        s.masks_empty    = False
        s.current_tissue = 1
        self._view.set_color(QColor(
            int(s.informacoes["colors"][0][0]),
            int(s.informacoes["colors"][0][1]),
            int(s.informacoes["colors"][0][2]),
        ))
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
            v.set_color(QColor(
                int(s.informacoes["colors"][0][0]),
                int(s.informacoes["colors"][0][1]),
                int(s.informacoes["colors"][0][2]),
            ))
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
            item, confirmed = QInputDialog.getItem(
                v, "Select the region to paint", "List of regions",
                ("Fat", "Intramuscular Fat", "Visceral Fat",
                 "Bone", "Muscle", "Organ", "Other"), 0, False
            )
            while not confirmed:
                item, confirmed = QInputDialog.getItem(
                    v, "Select the region to paint", "List of regions",
                    ("Fat", "Intramuscular Fat", "Visceral Fat",
                     "Bone", "Muscle", "Organ", "Other"), 0, False
                )
            s.informacoes["colors"].append(np.array([255, 255, 0]))
            s.informacoes["identifier"].append(1)
            s.informacoes["tissue"].append(dictTissues[item])
            s.current_tissue = 1
            v.current_tissue_label.setText(item)
            v.set_color(QColor(255, 255, 0))
            self._update_selected_hu()
            v.plotsuperpixelmask.UpdateView()

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

    def apply_clahe(self) -> None:
        s = self._state
        if np.array_equal(s.dicom_image_array, []):
            return
        self._reset_toggle()
        if s.masks_empty:
            self._view.plotsuperpixelmask.im = ""
        self._view.plotwidget_modify.HistMethodClahe()
        self._refresh_superpixel_panel()

    def apply_superpixel(self) -> None:
        self._reset_toggle()
        if not np.array_equal(self._state.dicom_image_array, []):
            self._view.plotsuperpixelmask.SuperPixel()
            self._state.toggle_available = True

    def remove_objects(self) -> None:
        s = self._state
        self._reset_toggle()
        if np.array_equal(s.dicom_image_array, []):
            return
        if s.masks_empty:
            self._view.plotsuperpixelmask.im = ""
        self._view.plotwidget_modify.DeleteObjects()
        self._refresh_superpixel_panel()

    def remove_skin(self) -> None:
        s = self._state
        self._reset_toggle()
        if np.array_equal(s.dicom_image_array, []):
            return
        if s.masks_empty:
            self._view.plotsuperpixelmask.im = ""
        self._view.plotwidget_modify.DeleteSkinAndObjects()
        self._refresh_superpixel_panel()

    def restore_original(self) -> None:
        s = self._state
        self._reset_toggle()
        if not s.file_name_global or s.file_name_global.split(".")[-1] == "csv":
            return
        self._view.plotwidget_modify.ResetDicom()
        if s.masks_empty:
            self._view.plotsuperpixelmask.im = ""
        self._refresh_superpixel_panel()

    def on_color_selected(self, color: QColor) -> None:
        """Lógica completa de seleção de cor/tecido."""
        s        = self._state
        v        = self._view
        selected = np.array([color.red(), color.green(), color.blue()])

        found, index = False, 0
        for i, c in enumerate(s.informacoes["colors"]):
            if np.array_equal(c, selected):
                tissue = s.informacoes["tissue"][i]
                for key, val in dictTissues.items():
                    if val == tissue:
                        v.current_tissue_label.setText(key)
                found, index = True, i
                break

        if found:
            s.current_tissue = index + 1
            v.set_color(color)
        else:
            item, ok = QInputDialog.getItem(
                v, "Select the region to paint", "List of regions",
                ("Fat", "Intramuscular Fat", "Visceral Fat",
                 "Bone", "Muscle", "Organ", "Other"), 0, False
            )
            if ok:
                v.set_color(color)
                if s.informacoes["tissue"].count(dictTissues[item]) > 0:
                    v.current_tissue_label.setText(item)
                    s.current_tissue = (
                        s.informacoes["tissue"].index(dictTissues[item]) + 1
                    )
                    s.informacoes["colors"][s.current_tissue - 1] = selected
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
                        v.plotsuperpixelmask.UpdateView()
                else:
                    size = len(s.informacoes["colors"])
                    s.informacoes["colors"].append(selected)
                    s.informacoes["identifier"].append(size + 1)
                    s.informacoes["tissue"].append(dictTissues[item])
                    s.current_tissue = size + 1
                    v.current_tissue_label.setText(item)

        self._update_selected_hu()
        v.plotsuperpixelmask.UpdateView()

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

    def _update_selected_hu(self) -> None:
        s      = self._state
        tissue = s.informacoes["tissue"][s.current_tissue - 1]
        if tissue in [1, 2, 3]:
            s.selected_hu = s.fat_hu
        elif tissue in [5]:
            s.selected_hu = s.muscle_hu
        else:
            s.selected_hu = np.ones(s.dicom_image_array.shape, dtype=bool)

    # ── segmentação automática ────────────────────────────────────────────────

    def available_ml_tissues(self) -> list:
        """
        Tecidos disponíveis para segmentação automática — só os que têm
        modelo efetivamente carregado (ver `ml_segmentation.load_all_models`,
        chamado no startup em app.py). Nunca inclui um tecido "registrado
        mas sem modelo carregado", pra evitar oferecer uma opção que vai
        falhar na hora de rodar.
        """
        return available_tissues()

    def tissue_has_color(self, tissue_key: str) -> bool:
        """
        Indica se `tissue_key` já tem uma cor associada nesta sessão
        (de pintura manual anterior ou de uma segmentação automática
        anterior). Se True, a view deve pular a etapa de escolha de cor
        e reaproveitar a cor existente — evita o mesmo tecido aparecer
        com cores diferentes na mesma máscara.
        """
        return dictTissues[tissue_key] in self._state.informacoes["tissue"]

    def _ensure_tissue_registered(self, tissue_key: str, color=None) -> int:
        """
        Garante que `tissue_key` existe em `informacoes`, retornando seu
        índice 1-based (mesmo valor usado em `segmented_mask`).

        Se o tecido já estiver registrado, `color` é ignorado e a cor
        existente é reaproveitada. Se ainda não estiver, `color` é
        obrigatório (a view deve ter perguntado antes, ver `tissue_has_color`).
        """
        s = self._state
        tissue_id = dictTissues[tissue_key]
        if tissue_id in s.informacoes["tissue"]:
            return s.informacoes["tissue"].index(tissue_id) + 1

        if color is None:
            raise ValueError(
                f"Tecido '{tissue_key}' ainda não registrado — é necessário informar uma cor."
            )
        size = len(s.informacoes["colors"])
        s.informacoes["colors"].append(np.array([color.red(), color.green(), color.blue()]))
        s.informacoes["identifier"].append(size + 1)
        s.informacoes["tissue"].append(tissue_id)
        return size + 1

    def run_ml_segmentation(self, tissue_key: str, color=None) -> bool:
        """
        Executa a segmentação automática para `tissue_key` e aplica o
        resultado como uma proposta PENDENTE: os pixels já aparecem
        pintados na máscara — de forma ADITIVA, sem apagar nenhum tecido
        já segmentado (manualmente ou por uma rodada anterior de
        segmentação automática) — mas o estado anterior fica salvo em
        `s.ml_snapshot` até o usuário decidir, via `accept_ml_segmentation`,
        `edit_ml_segmentation` ou `reject_ml_segmentation`.

        `color` só é usado (e obrigatório) se `tissue_key` ainda não tiver
        cor associada — ver `tissue_has_color`.

        Retorna True se a proposta foi gerada, False se não havia imagem
        carregada ou se a inferência falhou (nesse caso uma mensagem de
        erro já foi exibida ao usuário).
        """
        s = self._state
        if np.array_equal(s.dicom_image_array, []):
            return False

        try:
            predicted = predict_mask(s.dicom_image_array, tissue_key)
        except MLSegmentationError as e:
            QMessageBox.critical(
                self._view, "Erro na segmentação automática", str(e)
            )
            return False

        # snapshot do estado mutável anterior — permite "Rejeitar" sem
        # perder nada que já estava segmentado antes desta rodada.
        s.ml_snapshot = {
            "segmented_mask": copy.deepcopy(s.segmented_mask),
            "mask3d":         copy.deepcopy(s.mask3d),
            "informacoes":    copy.deepcopy(s.informacoes),
            "area":           s.area,
            "masks_empty":    s.masks_empty,
            "current_tissue": s.current_tissue,
        }

        # inicializa apenas se ainda não existir — NUNCA zera um
        # segmented_mask/mask3d que já tenha conteúdo de antes.
        if np.array_equal(s.segmented_mask, []):
            s.segmented_mask = np.zeros_like(s.dicom_image_array, dtype="uint8")
        if s.masks_empty:
            s.mask3d = np.zeros(
                (s.dicom_image_array.shape[0], s.dicom_image_array.shape[1], 3),
                dtype="uint8",
            )
            s.mask3d[:, :, 0] = s.dicom_image_array
            s.mask3d[:, :, 1] = s.dicom_image_array
            s.mask3d[:, :, 2] = s.dicom_image_array
            s.masks_empty = False

        tissue_index = self._ensure_tissue_registered(tissue_key, color)
        tissue_color = s.informacoes["colors"][tissue_index - 1]

        # escreve só nos pixels preditos — todo o resto de segmented_mask
        # (outros tecidos já segmentados) permanece intocado.
        s.segmented_mask[predicted] = tissue_index
        s.mask3d[:, :, 0] = np.where(predicted, tissue_color[0], s.mask3d[:, :, 0])
        s.mask3d[:, :, 1] = np.where(predicted, tissue_color[1], s.mask3d[:, :, 1])
        s.mask3d[:, :, 2] = np.where(predicted, tissue_color[2], s.mask3d[:, :, 2])

        s.current_tissue = tissue_index
        s.ml_pending = True
        self._view.plotsuperpixelmask.showSavedMask()
        return True

    def accept_ml_segmentation(self) -> None:
        """
        'Aceitar': incorpora a proposta ao estado de segmentação em
        memória — igual a uma pintura manual. NÃO salva em .csv (isso é
        feito à parte, via File → Save), justamente para permitir
        encadear várias segmentações automáticas de tecidos diferentes
        antes de salvar.
        """
        self._state.ml_pending  = False
        self._state.ml_snapshot = {}

    def edit_ml_segmentation(self) -> None:
        """
        'Editar': aceita a proposta como ponto de partida e já prepara a
        imagem para correção manual, gerando os superpixels — o usuário
        cai direto no modo de pintura, sem precisar acionar SuperPixel
        manualmente depois.
        """
        self._state.ml_pending  = False
        self._state.ml_snapshot = {}
        self._undo_stack.clear()
        self.apply_superpixel()

    def reject_ml_segmentation(self) -> None:
        """'Rejeitar': descarta a proposta, restaurando o estado anterior a ela."""
        s = self._state
        if not s.ml_pending:
            return
        snap = s.ml_snapshot

        s.segmented_mask = snap.get("segmented_mask", [])
        s.mask3d         = snap.get("mask3d", [])
        s.informacoes    = snap.get(
            "informacoes", {"colors": [], "identifier": [], "tissue": []}
        )
        s.area           = snap.get("area", s.area)
        s.masks_empty    = snap.get("masks_empty", True)
        s.current_tissue = snap.get("current_tissue", 0)

        s.ml_pending  = False
        s.ml_snapshot = {}

        if s.masks_empty:
            self._view.plotsuperpixelmask.im = ""
            self._view.plotsuperpixelmask.UpdateView()
        else:
            self._view.plotsuperpixelmask.showSavedMask()
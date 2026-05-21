import copy

import numpy as np
import pydicom
from PySide6 import QtGui
from PySide6.QtCore import Slot
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QColorDialog, QFileDialog, QHBoxLayout, QInputDialog,
    QLabel, QMainWindow, QMenu, QMessageBox, QVBoxLayout, QWidget, QApplication
)

from src.models.segmentation_state import SegmentationState
from src.models.tissue_config import dictTissues
from src.services.dicom_service import dicom2array
from src.services.mask_io import load_mask
from src.utils.image_utils import ConvertToUint8, tissue_segmentation
from src.services.image_processing import select_RoI
from src.views.dialogs import CustomDialog
from src.views.params_dialog import ParamsDialog
from src.views.percentages_widget import PercentagesGraph
from src.views.reference_panel import PlotWidgetModify
from src.views.superpixel_panel import PlotSuperPixelMask

from os import path


COLORS = [
    '#ffeeb9', '#bd4b4b', '#442242', '#1ab11d',
    '#286440', '#133542', '#675c85', '#251e3c',
    '#1e132c', '#b5b4d3', '#6b6a7c', '#232328',
]


class ImageViewer(QMainWindow):
    def __init__(self, state: SegmentationState):
        super().__init__()
        self._state = state

        # ── toolbar superior ──────────────────────────────────────────
        self.bar = self.addToolBar("Menu")
        from PySide6.QtCore import Qt
        self.bar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.color_action = QAction(self)
        self.color_action.triggered.connect(self.on_color_clicked)
        self.bar.addAction(self.color_action)
        self.set_color(QColor(255, 255, 0))
        self.bar.addWidget(QLabel(" Current tissue: "))
        self.current_tissue_label = QLabel("None")
        self.bar.addWidget(self.current_tissue_label)

        # ── painéis ───────────────────────────────────────────────────
        self.plotsuperpixelmask = PlotSuperPixelMask(
            state, self._mouse_event, self
        )
        self.plotwidget_modify = PlotWidgetModify(
            state, self._mouse_event, self
        )

        # ── layout ────────────────────────────────────────────────────
        layout2 = QVBoxLayout()
        layout2.addWidget(self.plotsuperpixelmask)
        layout3 = QVBoxLayout()
        layout3.addWidget(self.plotwidget_modify)

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(10)
        h_layout.addLayout(layout2)
        h_layout.addLayout(layout3)

        central = QWidget()
        central.setLayout(h_layout)
        self.setCentralWidget(central)

        self.setWindowTitle("LAMAC")
        self.setWindowIcon(QPixmap("./icon.png"))

        self._create_actions()
        self._create_menus()
        self._load_dirs()

    def _mouse_event(self, event, plot: int):
        """Callback de clique repassado pelos painéis."""
        from PySide6.QtCore import Qt as _Qt
        s = self._state
        zoom_ok = str(self.plotsuperpixelmask.toolbar._actions["zoom"]).__contains__("checked=false")
        pan_ok  = str(self.plotsuperpixelmask.toolbar._actions["pan"]).__contains__("checked=false")
        zoom_ok2 = str(self.plotwidget_modify.toolbar._actions["zoom"]).__contains__("checked=false")
        pan_ok2  = str(self.plotwidget_modify.toolbar._actions["pan"]).__contains__("checked=false")

        if (
            event.xdata is not None and event.ydata is not None
            and event.xdata > 1 and event.ydata > 1
            and s.superpixel_auth
            and (
                (zoom_ok and pan_ok and s.current_plot == 0)
                or (zoom_ok2 and pan_ok2 and s.current_plot == 1)
            )
        ):
            self._paint_superpixel(event.xdata, event.ydata, s.segments_global, plot)

    def _paint_superpixel(self, x, y, segments, plot: int):
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

        s.masks = np.zeros_like(s.dicom_image_array, dtype="bool")
        s.previous_paints.append(copy.deepcopy(s.mask3d))
        segment_id = segments[int(y)][int(x)]
        s.previous_segments["superpixel"].append(segment_id)
        s.previous_segments["previous_identifier"].append(s.segmented_mask[int(y)][int(x)])

        if len(s.previous_paints) == 11:
            s.previous_paints.pop(0)
            s.previous_segments["superpixel"].pop(0)
            s.previous_segments["previous_identifier"].pop(0)

        if (plot == 1 and s.undo == 1) or (plot == 2 and s.undo == 2) or s.undo == 3:
            s.masks = np.ones_like(s.dicom_image_array, dtype="bool")
            s.segmented_mask[segments == segments[int(y)][int(x)]] = 0
            s.masks[segments == segments[int(y)][int(x)]] = 0
            s.mask3d[:, :, 0] = (s.dicom_image_array * (~s.masks).astype('uint8')
                                  + s.mask3d[:, :, 0] * s.masks.astype('uint8'))
            s.mask3d[:, :, 1] = (s.dicom_image_array * (~s.masks).astype('uint8')
                                  + s.mask3d[:, :, 1] * s.masks.astype('uint8'))
            s.mask3d[:, :, 2] = (s.dicom_image_array * (~s.masks).astype('uint8')
                                  + s.mask3d[:, :, 2] * s.masks.astype('uint8'))
        else:
            hu_mask = np.ones_like(s.dicom_image_array, dtype=bool)
            if s.radio_density_check_enabled:
                tissue = s.informacoes["tissue"][s.current_tissue - 1]
                if tissue in [1, 2, 3]:
                    hu_mask = hu_mask * s.fat_hu
                elif tissue in [5]:
                    hu_mask = hu_mask * s.muscle_hu
            s.segmented_mask[(hu_mask * segments) == segments[int(y)][int(x)]] = s.current_tissue
            s.masks[(hu_mask * segments) == segments[int(y)][int(x)]] = 1
            color = s.informacoes["colors"][s.current_tissue - 1]
            s.mask3d[:, :, 0] = color[0] * s.masks + s.mask3d[:, :, 0] * (~s.masks).astype('uint8')
            s.mask3d[:, :, 1] = color[1] * s.masks + s.mask3d[:, :, 1] * (~s.masks).astype('uint8')
            s.mask3d[:, :, 2] = color[2] * s.masks + s.mask3d[:, :, 2] * (~s.masks).astype('uint8')

        self.plotsuperpixelmask.UpdateView()

    def open(self):
        s = self._state
        s.previous_segments = {"superpixel": [], "previous_identifier": []}
        s.previous_paints   = []
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open File", s.open_dir,
            filter="DICOM (*.dcm *.);;csv(*.csv)"
        )
        if not file_name:
            return
        s.file_name        = file_name
        s.file_name_global = file_name
        s.superpixel_auth  = False

        if file_name.split(".")[-1] == "csv":
            s.csv_flag = True
            s.segmented_mask, s.informacoes, s.area = load_mask(file_name)
            s.dicom_image_array = []
            s.masks_empty = False
            s.current_tissue = 1
            self.set_color(QColor(
                int(s.informacoes["colors"][0][0]),
                int(s.informacoes["colors"][0][1]),
                int(s.informacoes["colors"][0][2]),
            ))
            self.recoveryMask3d()
            self.plotwidget_modify.axes.clear()
            self.plotwidget_modify.axes.set_title("Imagem Conferência")
            self.plotwidget_modify.view.draw()
        else:
            dcm = pydicom.dcmread(file_name, force=True)
            s.dicom_image_array = dicom2array(dcm)
            if s.dicom_image_array is None:
                QMessageBox.critical(self, "Erro", "Não foi possível ler o arquivo DICOM.")
                return
            roi = select_RoI(s.dicom_image_array)
            s.muscle_hu   = tissue_segmentation(roi, "muscle")
            s.fat_hu      = tissue_segmentation(roi, "fat")
            s.selected_hu = np.ones(s.dicom_image_array.shape)
            s.dicom_image_array = ConvertToUint8(s.dicom_image_array)
            s.area = int(np.count_nonzero(ConvertToUint8(select_RoI(s.dicom_image_array))))
            self.plotwidget_modify.on_change()

            ok = 0
            if s.csv_flag:
                dlg = CustomDialog()
                ok  = dlg.show()

            if ok:
                s.current_tissue = 1
                self.set_color(QColor(
                    int(s.informacoes["colors"][0][0]),
                    int(s.informacoes["colors"][0][1]),
                    int(s.informacoes["colors"][0][2]),
                ))
                s.segments_global = []
                self.recoveryMask3d()
                s.masks_empty = False
            else:
                s.mask3d          = []
                self.plotsuperpixelmask.im = ""
                s.masks_empty     = True
                s.current_tissue  = 0
                s.segmented_mask  = []
                s.segments_global = []
                s.informacoes     = {"colors": [], "identifier": [], "tissue": []}
                item, ok = QInputDialog.getItem(
                    self, "Select the region to paint", "List of regions",
                    ("Fat", "Intramuscular Fat", "Visceral Fat",
                     "Bone", "Muscle", "Organ", "Other"), 0, False
                )
                while not ok:
                    item, ok = QInputDialog.getItem(
                        self, "Select the region to paint", "List of regions",
                        ("Fat", "Intramuscular Fat", "Visceral Fat",
                         "Bone", "Muscle", "Organ", "Other"), 0, False
                    )
                s.informacoes["colors"].append(np.array([255, 255, 0]))
                s.informacoes["identifier"].append(1)
                s.informacoes["tissue"].append(dictTissues[item])
                s.current_tissue = 1
                self.current_tissue_label.setText(item)
                self.set_color(QColor(255, 255, 0))
                tissue = s.informacoes["tissue"][s.current_tissue - 1]
                if tissue in [1, 2, 3]:
                    s.selected_hu = s.fat_hu
                elif tissue in [5]:
                    s.selected_hu = s.muscle_hu
                self.plotsuperpixelmask.UpdateView()
            s.csv_flag = False

    @Slot()
    def on_color_clicked(self, _layout=None):
        from PySide6.QtCore import Qt as _Qt
        s     = self._state
        color = QColorDialog.getColor(_Qt.black, self)
        qc    = QColor(color)
        if qc.red() == 0 and qc.green() == 0 and qc.blue() == 0:
            return
        selected = np.array([qc.red(), qc.green(), qc.blue()])
        found, index = False, 0
        for i, c in enumerate(s.informacoes["colors"]):
            if np.array_equal(c, selected):
                tissue = s.informacoes["tissue"][i]
                for key, val in dictTissues.items():
                    if val == tissue:
                        self.current_tissue_label.setText(key)
                found, index = True, i
                break
        if found:
            s.current_tissue = index + 1
            self.set_color(color)
        else:
            item, ok = QInputDialog.getItem(
                self, "Select the region to paint", "List of regions",
                ("Fat", "Intramuscular Fat", "Visceral Fat",
                 "Bone", "Muscle", "Organ", "Other"), 0, False
            )
            if ok:
                self.set_color(color)
                if s.informacoes["tissue"].count(dictTissues[item]) > 0:
                    self.current_tissue_label.setText(item)
                    s.current_tissue = s.informacoes["tissue"].index(dictTissues[item]) + 1
                    s.informacoes["colors"][s.current_tissue - 1] = selected
                    if not np.array_equal(s.mask3d, []):
                        s.masks = np.zeros_like(s.dicom_image_array, dtype="bool")
                        s.masks[s.segmented_mask == s.current_tissue] = 1
                        ct = s.current_tissue - 1
                        s.mask3d[:, :, 0] = s.informacoes['colors'][ct][0] * s.masks + s.mask3d[:, :, 0] * (~s.masks).astype('uint8')
                        s.mask3d[:, :, 1] = s.informacoes['colors'][ct][1] * s.masks + s.mask3d[:, :, 1] * (~s.masks).astype('uint8')
                        s.mask3d[:, :, 2] = s.informacoes['colors'][ct][2] * s.masks + s.mask3d[:, :, 2] * (~s.masks).astype('uint8')
                        self.plotsuperpixelmask.UpdateView()
                else:
                    size = len(s.informacoes["colors"])
                    s.informacoes["colors"].append(selected)
                    s.informacoes["identifier"].append(size + 1)
                    s.informacoes["tissue"].append(dictTissues[item])
                    s.current_tissue = size + 1
                    self.current_tissue_label.setText(item)

        tissue = s.informacoes["tissue"][s.current_tissue - 1]
        if tissue in [1, 2, 3]:
            s.selected_hu = s.fat_hu
        elif tissue in [5]:
            s.selected_hu = s.muscle_hu
        self.plotsuperpixelmask.UpdateView()

    def set_color(self, color: QColor):
        pix = QPixmap(20, 20)
        pix.fill(color)
        self.color_action.setIcon(QIcon(pix))

    def recoveryMask3d(self):
        s = self._state
        s.masks  = np.zeros_like(s.segmented_mask, dtype="bool")
        s.mask3d = np.zeros(
            (s.segmented_mask.shape[0], s.segmented_mask.shape[1], 3),
            dtype="uint8"
        )
        if s.file_name_global.split(".")[-1] == "dcm":
            s.mask3d[:, :, 0] = s.dicom_image_array
            s.mask3d[:, :, 1] = s.dicom_image_array
            s.mask3d[:, :, 2] = s.dicom_image_array
        for i in range(len(s.informacoes["tissue"])):
            s.masks = np.zeros_like(s.segmented_mask, dtype="bool")
            s.masks[s.segmented_mask == s.informacoes["identifier"][i]] = 1
            s.mask3d[:, :, 0] = s.informacoes['colors'][i][0] * s.masks + s.mask3d[:, :, 0] * (~s.masks).astype('uint8')
            s.mask3d[:, :, 1] = s.informacoes['colors'][i][1] * s.masks + s.mask3d[:, :, 1] * (~s.masks).astype('uint8')
            s.mask3d[:, :, 2] = s.informacoes['colors'][i][2] * s.masks + s.mask3d[:, :, 2] * (~s.masks).astype('uint8')
        self.plotsuperpixelmask.showSavedMask()

    def _reset_toggle(self):
        s = self._state
        s.show_superpixel  = True
        s.superpixel_auth  = False
        s.toggle_available = False

    def HistMethodCLAHE(self):
        s = self._state
        self._reset_toggle()
        if np.array_equal(s.dicom_image_array, []):
            return
        if s.masks_empty:
            self.plotsuperpixelmask.im = ""
        self.plotwidget_modify.HistMethodClahe()
        self._refresh_superpixel_panel()

    def SuperPixel(self):
        self._reset_toggle()
        if not np.array_equal(self._state.dicom_image_array, []):
            self.plotsuperpixelmask.SuperPixel()
            self._state.toggle_available = True

    def toggleRadioDensityCheck(self):
        if not np.array_equal(self._state.dicom_image_array, []):
            self._state.radio_density_check_enabled = not self._state.radio_density_check_enabled

    def OriginalImage(self):
        s = self._state
        self._reset_toggle()
        if s.file_name_global and not s.file_name_global.split(".")[-1] == "csv":
            self.plotwidget_modify.ResetDicom()
            if s.masks_empty:
                self.plotsuperpixelmask.im = ""
            self._refresh_superpixel_panel()

    def RemoveObjects(self):
        s = self._state
        self._reset_toggle()
        if not np.array_equal(s.dicom_image_array, []):
            if s.masks_empty:
                self.plotsuperpixelmask.im = ""
            self.plotwidget_modify.DeleteObjects()
            self._refresh_superpixel_panel()

    def RemoveSkin(self):
        s = self._state
        self._reset_toggle()
        if not np.array_equal(s.dicom_image_array, []):
            if s.masks_empty:
                self.plotsuperpixelmask.im = ""
            self.plotwidget_modify.DeleteSkinAndObjects()
            self._refresh_superpixel_panel()

    def _refresh_superpixel_panel(self):
        s = self._state
        if np.array_equal(s.segments_global, []) and not np.array_equal(s.mask3d, []):
            self.recoveryMask3d()
            self.plotsuperpixelmask.showSavedMask()
        elif not np.array_equal(s.mask3d, []):
            self.recoveryMask3d()
            self.plotsuperpixelmask.showSavedMask()
        else:
            self.plotsuperpixelmask.UpdateView()

    def resetMask3d(self):
        s = self._state
        if np.array_equal(s.dicom_image_array, []):
            return
        s.previous_paints = []
        s.mask3d = np.zeros(
            (s.dicom_image_array.shape[0], s.dicom_image_array.shape[1], 3),
            dtype="uint8"
        )
        s.mask3d[:, :, 0] = s.dicom_image_array
        s.mask3d[:, :, 1] = s.dicom_image_array
        s.mask3d[:, :, 2] = s.dicom_image_array
        s.masks_empty = False
        s.previous_paints.append(copy.deepcopy(s.mask3d))
        self.plotsuperpixelmask.UpdateView()

    def calculatePercentages(self):
        graph = PercentagesGraph(self._state)
        graph.calculatePercentages()
        graph.show()

    def toggleSuperPixelView(self):
        s = self._state
        if not s.toggle_available:
            QMessageBox.warning(self, "Aviso",
                                "Você precisa aplicar o SuperPixel antes de usar o Toggle.")
            return
        s.superpixel_auth  = not s.superpixel_auth
        s.show_superpixel  = not s.show_superpixel
        self.plotsuperpixelmask.UpdateView()

    def alternar(self):
        s = self._state
        if s.num_segments == 2000:
            s.num_segments = 500
        elif s.num_segments == 500:
            s.num_segments = 5000
        else:
            s.num_segments = 2000

    def changeOptions(self):
        dlg = ParamsDialog(self._state, self)
        dlg.exec()

    def setDefaultOpen(self):
        d = QFileDialog.getExistingDirectory(self)
        if d:
            self._state.open_dir = d
            with open("./defaultImageDir.txt", "w") as f:
                f.write(d)

    def setDefaultSave(self):
        d = QFileDialog.getExistingDirectory(self)
        if d:
            self._state.save_dir = d
            with open("./defaultMaskDir.txt", "w") as f:
                f.write(d)

    def _load_dirs(self):
        if path.exists("./defaultImageDir.txt"):
            with open("./defaultImageDir.txt") as f:
                self._state.open_dir = f.readline()
        if path.exists("./defaultMaskDir.txt"):
            with open("./defaultMaskDir.txt") as f:
                self._state.save_dir = f.readline()

    def about(self):
        QMessageBox.about(self, "LAMAC", "<p>Segmentador Manual!!!</p>")

    def _create_actions(self):
        self.openAct                  = QAction("&Open...", self, shortcut="Ctrl+O",        triggered=self.open)
        self.exitAct                  = QAction("E&xit",    self, shortcut="Ctrl+Q",        triggered=self.close)
        self.claheAct                 = QAction("&Hist CLAHE", self, shortcut="Ctrl+C",     triggered=self.HistMethodCLAHE)
        self.superpixelAct            = QAction("&SuperPixel", self, shortcut="Ctrl+Shift+S", triggered=self.SuperPixel)
        self.toggleDensityAct         = QAction("&Toggle RD check", self, shortcut="Ctrl+Shift+D", triggered=self.toggleRadioDensityCheck)
        self.originalImageAct         = QAction("&Original Image", self,                    triggered=self.OriginalImage)
        self.removeObjectsAct         = QAction("&Remove Objects", self, shortcut="Ctrl+R", triggered=self.RemoveObjects)
        self.removeSkinAct            = QAction("&Remove Skin and Objects", self, shortcut="Ctrl+Shift+R", triggered=self.RemoveSkin)
        self.saveAct                  = QAction("&Save", self, shortcut="Ctrl+S",           triggered=self.plotsuperpixelmask.toolbar.save_mask)
        self.backPaintAct             = QAction("&Back", self, shortcut="Ctrl+Z",           triggered=self.plotsuperpixelmask.toolbar.back_paint)
        self.toggleSuperpixelAct      = QAction("&Toggle SuperPixel View", self, shortcut="Ctrl+T", triggered=self.toggleSuperPixelView)
        self.changeOptionsAct         = QAction("&Change Options", self,                    triggered=self.changeOptions)
        self.calculatePercentagesAct  = QAction("&Calculate Percentages", self,             triggered=self.calculatePercentages)
        self.setDefaultOpenAct        = QAction("&Default Open Directory", self,            triggered=self.setDefaultOpen)
        self.setDefaultSaveAct        = QAction("&Default Save Directory", self,            triggered=self.setDefaultSave)
        self.alternarAct              = QAction("&Alternar", self, shortcut="Ctrl+F",       triggered=self.alternar)
        self.aboutAct                 = QAction("&About", self,                             triggered=self.about)
        self.aboutQtAct               = QAction("About &Qt", self,                          triggered=QApplication.instance().aboutQt)

    def _create_menus(self):
        file_menu = QMenu("&File", self)
        file_menu.addAction(self.openAct)
        file_menu.addAction(self.saveAct)
        file_menu.addAction(self.exitAct)

        view_menu = QMenu("&View", self)
        for act in [self.superpixelAct, self.toggleDensityAct, self.toggleSuperpixelAct,
                    self.claheAct, self.originalImageAct, self.removeObjectsAct,
                    self.removeSkinAct, self.backPaintAct, self.calculatePercentagesAct]:
            view_menu.addAction(act)

        options_menu = QMenu("&Options", self)
        for act in [self.changeOptionsAct, self.setDefaultOpenAct,
                    self.setDefaultSaveAct, self.alternarAct]:
            options_menu.addAction(act)

        help_menu = QMenu("&Help", self)
        help_menu.addAction(self.aboutAct)
        help_menu.addAction(self.aboutQtAct)

        for menu in [file_menu, view_menu, options_menu, help_menu]:
            self.menuBar().addMenu(menu)
import numpy as np
import pydicom
from PySide6 import QtGui
from PySide6.QtCore import Slot
from PySide6.QtCore import Qt as _Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QColorDialog, QFileDialog, QHBoxLayout, QInputDialog,
    QLabel, QMainWindow, QMenu, QMessageBox, QVBoxLayout, QWidget, QApplication
)

from src.models.segmentation_state import SegmentationState
from src.controllers.main_controller import MainController
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
    def __init__(self, state: SegmentationState, controller: MainController):
        super().__init__()
        self._state = state
        self._controller = controller
        controller.set_view(self)

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
        s = self._state
        zoom_ok  = str(self.plotsuperpixelmask.toolbar._actions["zoom"]).__contains__("checked=false")
        pan_ok   = str(self.plotsuperpixelmask.toolbar._actions["pan"]).__contains__("checked=false")
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
            self._controller.paint_superpixel(
                event.xdata, event.ydata, s.segments_global, plot
            )

    def open(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open File", self._state.open_dir,
            filter="DICOM (*.dcm *.);;csv(*.csv)"
        )
        if not file_name:
            return
        self._controller.open_file(file_name)

    @Slot()
    def on_color_clicked(self, _layout=None):
        from PySide6.QtCore import Qt as _Qt
        s     = self._state
        color = QColorDialog.getColor(_Qt.black, self)
        qc    = QColor(color)
        if qc.red() == 0 and qc.green() == 0 and qc.blue() == 0:
            return
        self._controller.on_color_selected(qc)

    def set_color(self, color: QColor):
        pix = QPixmap(20, 20)
        pix.fill(color)
        self.color_action.setIcon(QIcon(pix))

    def recoveryMask3d(self):
        self._controller.reset_mask3d()

    def HistMethodCLAHE(self):
        self._controller.apply_clahe()

    def SuperPixel(self):
        self._controller.apply_superpixel()

    def toggleRadioDensityCheck(self):
        if not np.array_equal(self._state.dicom_image_array, []):
            self._state.radio_density_check_enabled = not self._state.radio_density_check_enabled

    def OriginalImage(self):
        self._controller.restore_original()

    def RemoveObjects(self):
        self._controller.remove_objects()

    def RemoveSkin(self):
        self._controller.remove_skin()

    def resetMask3d(self):
        self._controller.reset_mask3d()

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

    # ── Actions e menus ───────────────────────────────────────────────

    def _create_actions(self):
        self.openAct                 = QAction("&Open...",                   self, shortcut="Ctrl+O",        triggered=self.open)
        self.exitAct                 = QAction("E&xit",                      self, shortcut="Ctrl+Q",        triggered=self.close)
        self.claheAct                = QAction("&Hist CLAHE",                self, shortcut="Ctrl+C",        triggered=self.HistMethodCLAHE)
        self.superpixelAct           = QAction("&SuperPixel",                self, shortcut="Ctrl+Shift+S",  triggered=self.SuperPixel)
        self.toggleDensityAct        = QAction("&Toggle RD check",           self, shortcut="Ctrl+Shift+D",  triggered=self.toggleRadioDensityCheck)
        self.originalImageAct        = QAction("&Original Image",            self,                           triggered=self.OriginalImage)
        self.removeObjectsAct        = QAction("&Remove Objects",            self, shortcut="Ctrl+R",        triggered=self.RemoveObjects)
        self.removeSkinAct           = QAction("&Remove Skin and Objects",   self, shortcut="Ctrl+Shift+R",  triggered=self.RemoveSkin)
        self.calculatePercentagesAct = QAction("&Calculate Percentages",     self,                           triggered=self.calculatePercentages)
        self.toggleSuperpixelAct     = QAction("&Toggle SuperPixel View",    self, shortcut="Ctrl+T",        triggered=self.toggleSuperPixelView)
        self.changeOptionsAct        = QAction("&Change Options",            self,                           triggered=self.changeOptions)
        self.setDefaultOpenAct       = QAction("&Default Open Directory",    self,                           triggered=self.setDefaultOpen)
        self.setDefaultSaveAct       = QAction("&Default Save Directory",    self,                           triggered=self.setDefaultSave)
        self.alternarAct             = QAction("&Alternar",                  self, shortcut="Ctrl+F",        triggered=self.alternar)
        self.aboutAct                = QAction("&About",                     self,                           triggered=self.about)
        self.aboutQtAct              = QAction("About &Qt",                  self,                           triggered=QApplication.instance().aboutQt)
        self.backPaintAct            = QAction("&Back", self, shortcut="Ctrl+Z", triggered=self._controller.back_paint)
        self.saveAct                 = QAction("&Save", self, shortcut="Ctrl+S", triggered=self._controller.save_mask_action)

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
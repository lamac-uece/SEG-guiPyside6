import numpy as np
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QFileDialog, QHBoxLayout,
    QLabel, QMainWindow, QMenu, QMessageBox, QVBoxLayout, QWidget,
)

from src.models.segmentation_state import SegmentationState
from src.controllers.main_controller import MainController
from src.views.params_dialog import ParamsDialog
from src.views.percentages_widget import PercentagesGraph
from src.views.reference_panel import PlotWidgetModify
from src.views.superpixel_panel import PlotSuperPixelMask


class ImageViewer(QMainWindow):
    def __init__(self, state: SegmentationState, controller: MainController):
        super().__init__()
        self._state      = state
        self._controller = controller
        controller.set_view(self)

        self.bar = self.addToolBar("Menu")
        self.bar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.color_action = QAction(self)
        self.color_action.triggered.connect(self.on_color_clicked)
        self.bar.addAction(self.color_action)
        self.set_color(QColor(255, 255, 0))
        self.bar.addWidget(QLabel(" Current tissue: "))
        self.current_tissue_label = QLabel("None")
        self.bar.addWidget(self.current_tissue_label)

        self.plotsuperpixelmask = PlotSuperPixelMask(
            state, self._mouse_event,
            on_back_paint=controller.back_paint,
            on_save_mask=controller.save_mask_action,
            parent=self,
        )
        self.plotwidget_modify = PlotWidgetModify(
            state, self._mouse_event,
            on_back_paint=controller.back_paint,
            on_save_mask=controller.save_mask_action,
            parent=self,
        )

        left  = QVBoxLayout()
        left.addWidget(self.plotsuperpixelmask)
        right = QVBoxLayout()
        right.addWidget(self.plotwidget_modify)

        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(10)
        h_layout.addLayout(left)
        h_layout.addLayout(right)

        central = QWidget()
        central.setLayout(h_layout)
        self.setCentralWidget(central)

        self.setWindowTitle("LAMAC")
        self.setWindowIcon(QPixmap("assets/icon.png"))

        self._create_actions()
        self._create_menus()
        controller.load_dirs()

    def _mouse_event(self, event, plot: int):
        s = self._state

        def _free(toolbar):
            return (
                "checked=false" in str(toolbar._actions.get("zoom", ""))
                and "checked=false" in str(toolbar._actions.get("pan", ""))
            )

        if (
            event.xdata is not None and event.ydata is not None
            and event.xdata > 1 and event.ydata > 1
            and s.superpixel_auth
            and (
                (_free(self.plotsuperpixelmask.toolbar) and s.current_plot == 0)
                or (_free(self.plotwidget_modify.toolbar) and s.current_plot == 1)
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
        if file_name:
            self._controller.open_file(file_name)

    @Slot()
    def on_color_clicked(self, _layout=None):
        color = QColorDialog.getColor(Qt.black, self)
        qc    = QColor(color)
        if qc.red() == 0 and qc.green() == 0 and qc.blue() == 0:
            return
        self._controller.on_color_selected(qc)

    def set_color(self, color: QColor):
        pix = QPixmap(20, 20)
        pix.fill(color)
        self.color_action.setIcon(QIcon(pix))

    def HistMethodCLAHE(self, checked: bool = False):
        self._controller.toggle_clahe(checked)

    def sync_clahe_action(self, enabled: bool):
        self.claheAct.setChecked(enabled)

    def SuperPixel(self):
        self._controller.apply_superpixel()

    def OriginalImage(self):
        self._controller.restore_original()

    def RemoveObjects(self):
        self._controller.remove_objects()

    def RemoveSkin(self):
        self._controller.remove_skin()

    def recoveryMask3d(self):
        self._controller.recovery_mask3d()

    def resetMask3d(self):
        self._controller.reset_mask3d()

    def toggleRadioDensityCheck(self):
        if not np.array_equal(self._state.dicom_image_array, []):
            self._state.radio_density_check_enabled = (
                not self._state.radio_density_check_enabled
            )

    def toggleSuperPixelView(self):
        s = self._state
        if not s.toggle_available:
            QMessageBox.warning(self, "Warning",
                                "You need to apply SuperPixel before using Toggle.")
            return
        s.superpixel_auth = not s.superpixel_auth
        s.show_superpixel = not s.show_superpixel
        self.plotsuperpixelmask.UpdateView()

    def calculatePercentages(self):
        self.graph = PercentagesGraph(self._state)
        self.graph.calculatePercentages()
        self.graph.show()

    def changeOptions(self):
        s   = self._state
        dlg = ParamsDialog(s, self)
        if dlg.exec():
            if dlg.clahe_params_changed and s.clahe_enabled:
                self._controller.reapply_clahe()
            if (
                dlg.slic_params_changed
                and not np.array_equal(s.dicom_image_array, [])
                and not np.array_equal(s.segments_global, [])
            ):
                self._controller.apply_superpixel()
            elif not (dlg.clahe_params_changed and s.clahe_enabled):
                # Cor/grossura/opacidade da malha e demais ajustes
                # apenas redesenham a malha, sem recomputar o SLIC.
                self.plotsuperpixelmask.UpdateView()

    def alternar(self):
        s = self._state
        if s.num_segments == 2000:
            s.num_segments = 500
        elif s.num_segments == 500:
            s.num_segments = 5000
        else:
            s.num_segments = 2000

    def setDefaultOpen(self):
        self._controller.set_default_open_dir(self)

    def setDefaultSave(self):
        self._controller.set_default_save_dir(self)

    def about(self):
        about_text = """
        <h3><b>SEG — Segmentador Manual de Imagens DICOM</b></h3>
        <p>Desenvolvido no <b>LAMAC</b> (Laboratório de Métodos e Análise Computacional - UECE).</p>
        
        <p>Esta ferramenta permite a segmentação manual e interativa de tecidos corporais 
        em imagens tomográficas (DICOM), gerando máscaras exportáveis para análises subsequentes.</p>
        
        <hr>
        
        <h4><b>Fluxo de Execução Recomendado:</b></h4>
        <ol>
            <li><b>Abrir Imagem:</b> Vá em <code>File &rarr; Open</code> (Ctrl+O) e selecione o arquivo <code>.dcm</code>.</li>
            <li><b>Pré-processamento (Opcional):</b> Utilize o menu <code>View</code> para remover objetos externos, pele ou aplicar a equalização adaptativa (CLAHE).</li>
            <li><b>Gerar Superpixels:</b> Ative <code>View &rarr; SuperPixel</code> (Ctrl+Shift+S) para subdividir a imagem usando o algoritmo SLIC.</li>
            <li><b>Segmentação/Pintura:</b> Selecione o tecido desejado na barra de ferramentas e clique nas regiões para colorir. Se preferir, ative a filtragem por densidade HU.</li>
            <li><b>Exportar:</b> Salve seu progresso em <code>File &rarr; Save</code> (Ctrl+S) para gerar o arquivo de máscara em <code>.csv</code>.</li>
        </ol>
        
        <hr>
        <p><small><b>Tecnologias principais:</b> PySide6, Scikit-Image, OpenCV, NumPy e PyDicom.</small></p>
        """
        
        QMessageBox.about(self, "Sobre o SEG", about_text)

    def _create_actions(self):
        c = self._controller
        self.openAct                 = QAction("&Open...",                self, shortcut="Ctrl+O",       triggered=self.open)
        self.exitAct                 = QAction("E&xit",                   self, shortcut="Ctrl+Q",       triggered=self.close)
        self.claheAct                = QAction("&Hist CLAHE",             self, shortcut="Ctrl+C",       triggered=self.HistMethodCLAHE)
        self.claheAct.setCheckable(True)
        self.superpixelAct           = QAction("&SuperPixel",             self, shortcut="Ctrl+Shift+S", triggered=self.SuperPixel)
        self.toggleDensityAct        = QAction("&Toggle RD check",        self, shortcut="Ctrl+Shift+D", triggered=self.toggleRadioDensityCheck)
        self.originalImageAct        = QAction("&Original Image",         self,                          triggered=self.OriginalImage)
        self.removeObjectsAct        = QAction("&Remove Objects",         self, shortcut="Ctrl+R",       triggered=self.RemoveObjects)
        self.removeSkinAct           = QAction("&Remove Skin and Objects", self, shortcut="Ctrl+Shift+R", triggered=self.RemoveSkin)
        self.saveAct                 = QAction("&Save",                   self, shortcut="Ctrl+S",       triggered=c.save_mask_action)
        self.backPaintAct            = QAction("&Back",                   self, shortcut="Ctrl+Z",       triggered=c.back_paint)
        self.toggleSuperpixelAct     = QAction("&Toggle SuperPixel View", self, shortcut="Ctrl+T",       triggered=self.toggleSuperPixelView)
        self.changeOptionsAct        = QAction("&Change Options",         self,                          triggered=self.changeOptions)
        self.calculatePercentagesAct = QAction("&Calculate Percentages",  self,                          triggered=self.calculatePercentages)
        self.setDefaultOpenAct       = QAction("&Default Open Directory", self,                          triggered=self.setDefaultOpen)
        self.setDefaultSaveAct       = QAction("&Default Save Directory", self,                          triggered=self.setDefaultSave)
        self.alternarAct             = QAction("&Alternar",               self, shortcut="Ctrl+F",       triggered=self.alternar)
        self.aboutAct                = QAction("&About",                  self,                          triggered=self.about)
        self.aboutQtAct              = QAction("About &Qt",               self,                          triggered=QApplication.instance().aboutQt)

    def _create_menus(self):
        file_menu = QMenu("&File", self)
        file_menu.addAction(self.openAct)
        file_menu.addAction(self.saveAct)
        file_menu.addAction(self.exitAct)

        view_menu = QMenu("&View", self)
        for act in [
            self.originalImageAct, self.removeObjectsAct, self.removeSkinAct,
            self.claheAct, self.superpixelAct, self.toggleDensityAct,
            self.toggleSuperpixelAct, self.backPaintAct, self.calculatePercentagesAct,
        ]:
            view_menu.addAction(act)

        options_menu = QMenu("&Options", self)
        for act in [
            self.changeOptionsAct, self.setDefaultOpenAct,
            self.setDefaultSaveAct, self.alternarAct,
        ]:
            options_menu.addAction(act)

        help_menu = QMenu("&Help", self)
        help_menu.addAction(self.aboutAct)
        help_menu.addAction(self.aboutQtAct)

        for menu in [file_menu, view_menu, options_menu, help_menu]:
            self.menuBar().addMenu(menu)
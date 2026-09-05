import numpy as np
from PySide6.QtCore import QSize, Qt, Slot
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QDialogButtonBox, QFileDialog,
    QHBoxLayout, QLabel, QMainWindow, QMenu, QMessageBox, QPushButton,
    QStackedWidget, QTabWidget, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from src.models.segmentation_state import SegmentationState
from src.controllers.main_controller import MainController
from src.views.icons import make_icon
from src.views.params_dialog import OptionsPanel
from src.views.percentages_widget import PercentagesGraph
from src.views.superpixel_panel import PlotSuperPixelMask
from src.views.tissue_palette import TissuePalette


class ImageViewer(QMainWindow):
    def __init__(self, state: SegmentationState, controller: MainController):
        super().__init__()
        self._state      = state
        self._controller = controller
        controller.set_view(self)

        self._build_canvas()
        self._build_rail()
        self._build_right_panel()
        self._build_central_layout()
        self._build_top_bar()
        self._create_actions()
        self._build_menus()

        self.setWindowTitle("SuperSeg — Segmentação DICOM")
        self.setWindowIcon(QPixmap("assets/icon.png"))
        controller.load_dirs()

    # ── construção dos blocos ────────────────────────────────────────────────
    def _build_canvas(self):
        self.plotsuperpixelmask = PlotSuperPixelMask(
            self._state, self._mouse_event,
            parent=self,
        )

    def _build_rail(self):
        self.rail = QToolBar("Tools")
        self.rail.setObjectName("ToolsRail")
        self.rail.setOrientation(Qt.Vertical)
        self.rail.setMovable(False)
        self.rail.setIconSize(QSize(26, 26))
        self.rail.setToolButtonStyle(Qt.ToolButtonIconOnly)

        # ferramentas de pintura: pincel (padrão) e borracha, exclusivas
        self.tool_group = QActionGroup(self)
        self.tool_group.setExclusive(True)

        self.brush_act = QAction(make_icon("brush"), "Pincel", self)
        self.brush_act.setCheckable(True)
        self.brush_act.setChecked(True)
        self.brush_act.setToolTip("Pincel — pintar tecido")
        self.tool_group.addAction(self.brush_act)

        self.eraser_act = QAction(make_icon("eraser"), "Borracha", self)
        self.eraser_act.setCheckable(True)
        self.eraser_act.setToolTip(
            "Borracha — apagar a pintura de um superpixel (clique único)"
        )
        self.tool_group.addAction(self.eraser_act)

        self.tool_group.triggered.connect(self._tool_changed)
        self.rail.addActions([self.brush_act, self.eraser_act])
        self.rail.addSeparator()

        # remover objetos / pele (menu dropdown)
        self.remove_btn = QToolButton(self)
        self.remove_btn.setIcon(make_icon("wand"))
        self.remove_btn.setPopupMode(QToolButton.InstantPopup)
        self.remove_btn.setToolTip("Remover objetos / pele")
        menu = QMenu(self)
        menu.addAction(self._action("removeObjects", "Remover objetos externos",
                                    make_icon("wand"), self.RemoveObjects))
        menu.addAction(self._action("removeSkin", "Remover pele e objetos",
                                    make_icon("wand"), self.RemoveSkin))
        self.remove_btn.setMenu(menu)
        self.rail.addWidget(self.remove_btn)

        # restaurar imagem original (lixeira)
        self.restore_act = QAction(QIcon("assets/trash.png"), "Restaurar imagem original", self)
        self.restore_act.setToolTip("Restaurar imagem original")
        self.restore_act.triggered.connect(self.OriginalImage)
        self.rail.addAction(self.restore_act)
        self.rail.addSeparator()

        # Options (parâmetros SLIC/CLAHE/malha) sobrepondo o painel direito
        self.options_act = QAction(make_icon("options"), "Options", self)
        self.options_act.setToolTip("Options — parâmetros SLIC/CLAHE/malha")
        self.options_act.triggered.connect(self._open_options)
        self.rail.addAction(self.options_act)

    def _build_right_panel(self):
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # ── Segmentação ──
        self.tissue_palette = TissuePalette(
            self,
            on_select=self._controller.select_tissue,
            on_color_change=self._controller.on_color_selected,
        )
        self.current_tissue_label = self.tissue_palette.current_tissue_label
        self.tabs.addTab(self.tissue_palette, "Segmentação")

        # ── Índices ──
        self.indices_graph = PercentagesGraph(self._state)
        refresh_btn = QPushButton("Atualizar índices")
        refresh_btn.clicked.connect(self._recalc_indices)
        indices_page = QWidget()
        v = QVBoxLayout(indices_page)
        v.setContentsMargins(4, 4, 4, 4)
        v.addWidget(self.indices_graph, 1)
        v.addWidget(refresh_btn)
        self.tabs.addTab(indices_page, "Índices")

        # ── Comparação ──
        comp_page = QWidget()
        cv = QVBoxLayout(comp_page)
        cv.setContentsMargins(8, 8, 8, 8)
        title = QLabel("Comparação")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        info = QLabel(
            "A imagem central agora mostra o pré-processamento atual "
            "(sem pintura e sem malha), como na antiga imagem de conferência.\n\n"
            "Esta vista é somente leitura. Volte para a aba Segmentação para "
            "continuar pintando."
        )
        info.setWordWrap(True)
        cv.addWidget(title)
        cv.addWidget(info)
        cv.addStretch(1)
        self.tabs.addTab(comp_page, "Comparação")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        # ── stack: abas / options ──
        self.right_stack = QStackedWidget()
        self.right_stack.addWidget(self.tabs)
        self.right_stack.setMinimumWidth(250)
        self.right_stack.setMaximumWidth(340)

    def _build_central_layout(self):
        central = QWidget()
        h = QHBoxLayout(central)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self.rail)
        h.addWidget(self.plotsuperpixelmask, 1)
        h.addWidget(self.right_stack)
        self.setCentralWidget(central)

    def _build_top_bar(self):
        bar = QToolBar("Top")
        bar.setMovable(False)
        bar.setObjectName("TopBar")
        bar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(bar)

        brand = QLabel("  SuperSeg ")
        brand.setStyleSheet("font-weight: bold; font-size: 14px;")
        bar.addWidget(brand)
        bar.addSeparator()

        self.undo_top_act = QAction(make_icon("undo"), "Undo", self)
        self.undo_top_act.setToolTip("Desfazer última pintura (Ctrl+Z)")
        self.undo_top_act.triggered.connect(self._controller.back_paint)
        bar.addAction(self.undo_top_act)

        self.save_top_act = QAction(make_icon("save"), "Salvar", self)
        self.save_top_act.setToolTip("Salvar máscara (Ctrl+S)")
        self.save_top_act.triggered.connect(self._controller.save_mask_action)
        bar.addAction(self.save_top_act)

        bar.addSeparator()

        self.clahe_top_act = QAction(make_icon("clahe"), "CLAHE", self)
        self.clahe_top_act.setCheckable(True)
        self.clahe_top_act.setToolTip("Ligar/desligar CLAHE (Ctrl+C)")
        self.clahe_top_act.triggered.connect(self.HistMethodCLAHE)
        bar.addAction(self.clahe_top_act)

        self.superpixel_top_act = QAction(make_icon("superpixel"), "SuperPixel", self)
        self.superpixel_top_act.setToolTip("Aplicar SuperPixel (Ctrl+Shift+S)")
        self.superpixel_top_act.triggered.connect(self.SuperPixel)
        bar.addAction(self.superpixel_top_act)

        bar.addSeparator()

        self.settings_act = QAction(make_icon("gear"), "Configurações", self)
        self.settings_act.setToolTip("Configurações (diretórios, RD check…)")
        self.settings_act.triggered.connect(self._open_settings)
        bar.addAction(self.settings_act)

    def _action(self, name, text, icon, slot) -> QAction:
        act = QAction(icon, text, self)
        act.triggered.connect(slot)
        return act

    # ── ações e menus ────────────────────────────────────────────────────────
    def _create_actions(self):
        c = self._controller
        self.openAct       = QAction("&Open...", self, shortcut="Ctrl+O", triggered=self.open)
        self.exitAct       = QAction("E&xit",    self, shortcut="Ctrl+Q", triggered=self.close)
        self.saveAct       = QAction("&Save",    self, shortcut="Ctrl+S", triggered=c.save_mask_action)
        self.claheAct      = QAction("&Hist CLAHE", self, shortcut="Ctrl+C", triggered=self.HistMethodCLAHE)
        self.claheAct.setCheckable(True)
        self.superpixelAct = QAction("&SuperPixel", self, shortcut="Ctrl+Shift+S", triggered=self.SuperPixel)
        self.toggleDensityAct = QAction("&Toggle RD check", self, shortcut="Ctrl+Shift+D", triggered=self.toggleRadioDensityCheck)
        self.originalImageAct = QAction("&Original Image", self, triggered=self.OriginalImage)
        self.removeObjectsAct = QAction("&Remove Objects", self, shortcut="Ctrl+R", triggered=self.RemoveObjects)
        self.removeSkinAct = QAction("&Remove Skin and Objects", self, shortcut="Ctrl+Shift+R", triggered=self.RemoveSkin)
        self.backPaintAct = QAction("&Back", self, shortcut="Ctrl+Z", triggered=c.back_paint)
        self.changeOptionsAct = QAction("&Change Options", self, triggered=self._open_options)
        self.setDefaultOpenAct = QAction("&Default Open Directory", self, triggered=self.setDefaultOpen)
        self.setDefaultSaveAct = QAction("&Default Save Directory", self, triggered=self.setDefaultSave)
        self.alternarAct = QAction("&Alternar", self, shortcut="Ctrl+F", triggered=self.alternar)
        self.aboutAct = QAction("&About", self, triggered=self.about)
        self.aboutQtAct = QAction("About &Qt", self, triggered=QApplication.instance().aboutQt)

        # registra ações fora dos menus para manter atalhos ativos
        for act in [
            self.openAct, self.exitAct, self.saveAct, self.claheAct,
            self.superpixelAct, self.toggleDensityAct, self.originalImageAct,
            self.removeObjectsAct, self.removeSkinAct, self.backPaintAct,
            self.changeOptionsAct, self.alternarAct,
        ]:
            self.addAction(act)

    def _build_menus(self):
        file_menu = QMenu("&File", self)
        file_menu.addAction(self.openAct)
        file_menu.addAction(self.saveAct)
        file_menu.addSeparator()
        file_menu.addAction(self.exitAct)

        help_menu = QMenu("&Help", self)
        help_menu.addAction(self.aboutAct)
        help_menu.addAction(self.aboutQtAct)

        for menu in [file_menu, help_menu]:
            self.menuBar().addMenu(menu)

    # ── ferramentas ──────────────────────────────────────────────────────────
    @Slot()
    def _tool_changed(self):
        toolbar = self.plotsuperpixelmask.toolbar
        if self.eraser_act.isChecked():
            if not toolbar.undo:
                toolbar.change_undo()
        else:
            if toolbar.undo:
                toolbar.change_undo()

    def _mouse_event(self, event, plot: int):
        canvas = self.plotsuperpixelmask
        if canvas.comparison_active:
            return
        s = self._state
        if (event.xdata is None or event.ydata is None
                or event.xdata <= 1 or event.ydata <= 1):
            return
        if not s.superpixel_auth:
            return
        if not self._free(canvas.toolbar):
            return
        self._controller.paint_superpixel(
            event.xdata, event.ydata, s.segments_global, 1
        )

    @staticmethod
    def _free(toolbar) -> bool:
        return (
            "checked=false" in str(toolbar._actions.get("zoom", ""))
            and "checked=false" in str(toolbar._actions.get("pan", ""))
        )

    # ── abas / comparação ────────────────────────────────────────────────────
    def _on_tab_changed(self, index: int):
        if index == 1:
            self._recalc_indices()
        self.plotsuperpixelmask.show_comparison(index == 2)

    def _recalc_indices(self):
        self.indices_graph.calculatePercentages()

    # ── options (painel sobreposto) ──────────────────────────────────────────
    def _open_options(self):
        old = self.right_stack.widget(1)
        if old is not None:
            old.deleteLater()
        panel = OptionsPanel(
            self._state,
            on_apply=self._apply_options,
            on_cancel=self._close_options,
        )
        self.right_stack.insertWidget(1, panel)
        self.right_stack.setCurrentIndex(1)

    def _apply_options(self):
        s = self._state
        panel = self.right_stack.widget(1)
        slic_changed, clahe_changed = panel.apply()

        if clahe_changed and s.clahe_enabled:
            self._controller.reapply_clahe()
        if slic_changed:
            # recomputar o SLIC deve voltar para a vista de trabalho
            if self.tabs.currentIndex() != 0:
                self.tabs.setCurrentIndex(0)
            if (not np.array_equal(s.dicom_image_array, [])
                    and not np.array_equal(s.segments_global, [])):
                self._controller.apply_superpixel()
        elif not (clahe_changed and s.clahe_enabled):
            # Cor/grossura/opacidade da malha e demais ajustes apenas redesenham
            self.plotsuperpixelmask.UpdateView()
        self._close_options()

    def _close_options(self):
        self.right_stack.setCurrentIndex(0)

    # ── config (engrenagem) ──────────────────────────────────────────────────
    def _open_settings(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Configurações")
        layout = QVBoxLayout(dlg)

        rd_check = QCheckBox("RD check — filtro por densidade HU (somente para testes)")
        rd_check.setChecked(self._state.radio_density_check_enabled)
        rd_check.toggled.connect(self.toggleRadioDensityCheck)
        layout.addWidget(rd_check)

        btn_alternar = QPushButton(f"Alternar num_segments (atual: {self._state.num_segments})")
        btn_alternar.clicked.connect(self.alternar)
        layout.addWidget(btn_alternar)

        btn_open_dir = QPushButton("Set Default Open Directory…")
        btn_open_dir.clicked.connect(lambda: self.setDefaultOpen())
        layout.addWidget(btn_open_dir)

        btn_save_dir = QPushButton("Set Default Save Directory…")
        btn_save_dir.clicked.connect(lambda: self.setDefaultSave())
        layout.addWidget(btn_save_dir)

        layout.addSpacing(8)
        btn_reset = QPushButton("Reset máscara 3D")
        btn_reset.clicked.connect(self.resetMask3d)
        layout.addWidget(btn_reset)
        btn_recovery = QPushButton("Recovery máscara 3D")
        btn_recovery.clicked.connect(self.recoveryMask3d)
        layout.addWidget(btn_recovery)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(dlg.reject)
        btns.clicked.connect(dlg.reject)
        layout.addWidget(btns)
        dlg.exec()

    # ── ações de imagem ──────────────────────────────────────────────────────
    def open(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open File", self._state.open_dir,
            filter="DICOM (*.dcm *.);;csv(*.csv)"
        )
        if file_name:
            self._controller.open_file(file_name)

    @Slot()
    def HistMethodCLAHE(self, checked: bool = False):
        self._controller.toggle_clahe(checked)

    def sync_clahe_action(self, enabled: bool):
        self.claheAct.setChecked(enabled)
        self.clahe_top_act.setChecked(enabled)

    def SuperPixel(self):
        if self.tabs.currentIndex() != 0:
            self.tabs.setCurrentIndex(0)
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

    def toggleRadioDensityCheck(self, checked=None):
        s = self._state
        if not np.array_equal(s.dicom_image_array, []):
            s.radio_density_check_enabled = (
                not s.radio_density_check_enabled
                if checked is None else bool(checked)
            )

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

    # ── sincronização com o controller ──────────────────────────────────────
    def sync_tissue_palette(self):
        self.tissue_palette.refresh(self._state)

    def set_color(self, color: QColor):
        self.tissue_palette.set_current_color(
            [color.red(), color.green(), color.blue()]
        )

    # ── sobre ────────────────────────────────────────────────────────────────
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
            <li><b>Pré-processamento (Opcional):</b> Remova objetos/pele ou aplique o CLAHE pelos botões da interface.</li>
            <li><b>Gerar Superpixels:</b> Clique em <b>SuperPixel</b> (Ctrl+Shift+S) para subdividir a imagem usando o SLIC.</li>
            <li><b>Segmentação/Pintura:</b> Selecione o tecido na aba Segmentação e pinte os superpixels no centro. A borracha apaga superpixels individuais.</li>
            <li><b>Exportar:</b> Salve seu progresso em <code>File &rarr; Save</code> (Ctrl+S) para gerar a máscara em <code>.csv</code>.</li>
        </ol>

        <hr>
        <p><small><b>Tecnologias principais:</b> PySide6, Scikit-Image, OpenCV, NumPy e PyDicom.</small></p>
        """
        QMessageBox.about(self, "Sobre o SEG", about_text)

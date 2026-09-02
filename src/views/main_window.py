import numpy as np
from PySide6.QtCore import Qt, QThreadPool, Slot
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QFileDialog, QHBoxLayout,
    QInputDialog, QLabel, QMainWindow, QMenu, QMessageBox, QVBoxLayout, QWidget,
)

from src.models.segmentation_state import SegmentationState
from src.controllers.main_controller import MainController
from src.views.dialogs import MLReviewDialog, MLTissueSelectionDialog
from src.views.params_dialog import ParamsDialog
from src.views.percentages_widget import PercentagesGraph
from src.views.reference_panel import PlotWidgetModify
from src.views.superpixel_panel import PlotSuperPixelMask
from src.workers.inference_worker import InferenceWorker


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

    def HistMethodCLAHE(self):
        self._controller.apply_clahe()

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

    def runSemiAutoSegmentation(self):
        """
        Fluxo da Segmentação Semi-Auto (1 tecido por vez, D3):
        1. exige uma imagem DICOM carregada (aviso caso contrário);
        2. pergunta qual tecido segmentar — só lista tecidos com modelo
           efetivamente carregado (ver `available_ml_tissues`);
        3. pergunta a cor do tecido, só se ele ainda não tiver uma
           associada nesta sessão — senão reaproveita a cor existente;
        4. roda o modelo num worker (não trava a UI) e, quando terminar,
           exibe o resultado sobreposto à imagem, sem apagar nenhum
           tecido já segmentado antes;
        5. pergunta a decisão do usuário (Aceitar / Editar / Rejeitar) e
           delega ao controller. O usuário pode repetir esse fluxo em
           seguida para outro tecido, normalmente.
        """
        s = self._state
        c = self._controller

        if np.array_equal(s.dicom_image_array, []):
            QMessageBox.warning(
                self, "Aviso",
                "Carregue uma imagem DICOM antes de usar a Segmentação Semi-Auto."
            )
            return

        tissues = c.available_ml_tissues()
        if not tissues:
            QMessageBox.warning(
                self, "Aviso", "Nenhum modelo de segmentação automática está carregado."
            )
            return

        tissue, confirmed = QInputDialog.getItem(
            self, "Segmentação Semi-Auto", "Tecido a segmentar", tissues, 0, False
        )
        if not confirmed:
            return

        color = None
        if not c.tissue_has_color(tissue):
            qc = QColorDialog.getColor(Qt.yellow, self, f"Cor para '{tissue}'")
            if not qc.isValid():
                return
            color = qc

        self._run_ml_worker(
            c.predict_ml_single, (tissue,),
            on_success=lambda predicted: self._review_ml_single(tissue, predicted, color),
        )

    def _review_ml_single(self, tissue: str, predicted, color) -> None:
        c = self._controller
        c.apply_ml_prediction(tissue, predicted, color)
        choice = MLReviewDialog(tissue, self).show()
        if choice == "accept":
            c.accept_ml_segmentation()
        elif choice == "edit":
            c.edit_ml_segmentation()
        else:
            # "reject" ou diálogo fechado sem escolha explícita:
            # por segurança, não deixamos uma proposta pendente sem decisão.
            c.reject_ml_segmentation()

    def runBatchAutoSegmentation(self):
        """
        Fluxo da Segmentação Auto (multiclasse em lote, D4):
        1. exige uma imagem DICOM carregada;
        2. diálogo de seleção dos tecidos a aplicar (default: todos os
           cobertos pelo modelo do modo Auto — ver `available_ml_batch_tissues`);
        3. pergunta a cor só dos tecidos selecionados que ainda não
           tiverem uma associada;
        4. roda 1 única inferência (worker, não trava a UI) para todos os
           tecidos selecionados;
        5. aplica e revisa cada tecido, um de cada vez, reaproveitando
           MLReviewDialog — igual ao Semi-Auto, só que em sequência.
        """
        s = self._state
        c = self._controller

        if np.array_equal(s.dicom_image_array, []):
            QMessageBox.warning(
                self, "Aviso",
                "Carregue uma imagem DICOM antes de usar a Segmentação Auto."
            )
            return

        tissues = c.available_ml_batch_tissues()
        if not tissues:
            QMessageBox.warning(
                self, "Aviso", "Nenhum modelo de segmentação Auto está carregado."
            )
            return

        selected = MLTissueSelectionDialog(tissues, self).show()
        if not selected:
            return

        colors = {}
        for tissue in selected:
            if not c.tissue_has_color(tissue):
                qc = QColorDialog.getColor(Qt.yellow, self, f"Cor para '{tissue}'")
                if not qc.isValid():
                    return
                colors[tissue] = qc

        self._run_ml_worker(
            c.predict_ml_batch, (selected,),
            on_success=lambda predictions: self._review_ml_batch(predictions, colors),
        )

    def _review_ml_batch(self, predictions: dict, colors: dict) -> None:
        c = self._controller
        for tissue, predicted in predictions.items():
            c.apply_ml_prediction(tissue, predicted, colors.get(tissue))
            choice = MLReviewDialog(tissue, self).show()
            if choice == "accept":
                c.accept_ml_segmentation()
            elif choice == "edit":
                c.edit_ml_segmentation()
                # Editar troca para o modo de correção manual (superpixels)
                # — não dá pra continuar revisando os próximos tecidos do
                # lote nesse mesmo fluxo; os que ainda não foram
                # processados simplesmente não são aplicados (o usuário
                # pode rodar a Segmentação Auto de novo depois, se quiser).
                break
            else:
                c.reject_ml_segmentation()

    # ── worker de inferência (não bloqueia a UI) ──────────────────────────────

    def _run_ml_worker(self, fn, args: tuple, on_success) -> None:
        """
        Roda `fn(*args)` — uma chamada de inferência pura, ver
        `MainController.predict_ml_single`/`predict_ml_batch` — numa
        thread do QThreadPool, e chama `on_success(resultado)` na thread
        principal quando terminar. Desabilita as ações de ML enquanto
        roda, para evitar disparar duas inferências ao mesmo tempo.
        """
        self.setCursor(Qt.WaitCursor)
        self._set_ml_actions_enabled(False)

        worker = InferenceWorker(fn, *args)
        worker.signals.finished.connect(self._make_ml_success_handler(on_success))
        worker.signals.failed.connect(self._on_ml_worker_failed)
        QThreadPool.globalInstance().start(worker)

    def _make_ml_success_handler(self, on_success):
        def handler(result):
            self.unsetCursor()
            self._set_ml_actions_enabled(True)
            on_success(result)
        return handler

    def _on_ml_worker_failed(self, message: str) -> None:
        self.unsetCursor()
        self._set_ml_actions_enabled(True)
        QMessageBox.critical(self, "Erro na segmentação automática", message)

    def _set_ml_actions_enabled(self, enabled: bool) -> None:
        self.autoSegmentAct.setEnabled(enabled)
        self.autoBatchSegmentAct.setEnabled(enabled)

    def calculatePercentages(self):
        self.graph = PercentagesGraph(self._state)
        self.graph.calculatePercentages()
        self.graph.show()

    def changeOptions(self):
        if ParamsDialog(self._state, self).exec():
            # Cor/grossura/opacidade da malha não exigem recomputar o SLIC
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
        self.superpixelAct           = QAction("&SuperPixel",             self, shortcut="Ctrl+Shift+S", triggered=self.SuperPixel)
        self.autoSegmentAct          = QAction("&Segmentação Semi-Auto", self, shortcut="Ctrl+Shift+A", triggered=self.runSemiAutoSegmentation)
        self.autoBatchSegmentAct     = QAction("&Segmentação Auto",      self, shortcut="Ctrl+Shift+B", triggered=self.runBatchAutoSegmentation)
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
            self.claheAct, self.superpixelAct, self.autoSegmentAct, self.autoBatchSegmentAct,
            self.toggleDensityAct, self.toggleSuperpixelAct, self.backPaintAct,
            self.calculatePercentagesAct,
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
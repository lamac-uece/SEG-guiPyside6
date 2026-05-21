from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QDoubleSpinBox, QHBoxLayout,
    QLabel, QLineEdit, QVBoxLayout,
)
from PySide6.QtGui import QIntValidator
from src.models.segmentation_state import SegmentationState

class ParamsDialog(QDialog):
    """Dialog de configuração de parâmetros SLIC, CLAHE e remoção de pele."""

    def __init__(self, state: SegmentationState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setWindowTitle("Parâmetros")
        self._build_ui()

    def _build_ui(self):
        s = self._state

        # ── Labels de seção ───────────────────────────────────────────
        lbl_superpixel = QLabel("<h1>Superpixel</h1>")
        lbl_clahe      = QLabel("<h1>Clahe</h1>")
        lbl_skin       = QLabel("<h1>Skin Segmentation</h1>")

        # ── Campos SLIC ───────────────────────────────────────────────
        self.input_segments    = QLineEdit(str(s.num_segments))
        self.input_segments.setValidator(QIntValidator(1000, 10000))

        self.input_compactness = QDoubleSpinBox()
        self.input_compactness.setValue(s.compactness)
        self.input_compactness.setMaximum(100)

        self.input_sigma       = QLineEdit(str(s.sigma_slic))
        self.input_sigma.setValidator(QIntValidator(0, 10))

        self.input_max_iter    = QLineEdit(str(s.max_num_iter))
        self.input_max_iter.setValidator(QIntValidator(1, 100))

        self.input_min_size    = QDoubleSpinBox()
        self.input_min_size.setValue(s.min_size_factor)
        self.input_min_size.setMaximum(100)

        self.input_max_size    = QDoubleSpinBox()
        self.input_max_size.setValue(s.max_size_factor)
        self.input_max_size.setMaximum(100)

        # ── Campos CLAHE ──────────────────────────────────────────────
        self.input_clip_limit  = QDoubleSpinBox()
        self.input_clip_limit.setValue(s.clip_limit)
        self.input_clip_limit.setMaximum(10)

        self.input_nbins       = QLineEdit(str(s.nbins))
        self.input_nbins.setValidator(QIntValidator(0, 1024))

        # ── Campos Skin ───────────────────────────────────────────────
        self.input_multiplier  = QDoubleSpinBox()
        self.input_multiplier.setValue(s.multiplicator)
        self.input_multiplier.setMaximum(3)

        # ── Botões ────────────────────────────────────────────────────
        buttons = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        # ── Layout ────────────────────────────────────────────────────
        def row(label_text, widget):
            h = QHBoxLayout()
            h.addWidget(QLabel(label_text))
            h.addWidget(widget)
            return h

        layout = QVBoxLayout(self)
        layout.addWidget(lbl_superpixel)
        layout.addLayout(row("Superpixels",          self.input_segments))
        layout.addLayout(row("Compactness",          self.input_compactness))
        layout.addLayout(row("Sigma",                self.input_sigma))
        layout.addLayout(row("max_num_iter",         self.input_max_iter))
        layout.addLayout(row("min_size_factor",      self.input_min_size))
        layout.addLayout(row("max_size_factor",      self.input_max_size))
        layout.addWidget(lbl_clahe)
        layout.addLayout(row("Clip limit (CLAHE)",   self.input_clip_limit))
        layout.addLayout(row("nbins",                self.input_nbins))
        layout.addWidget(lbl_skin)
        layout.addLayout(row("Cumulative sum multiplicator", self.input_multiplier))
        layout.addWidget(buttons)
        self.setLayout(layout)
    def _on_accept(self):
        s = self._state
        s.num_segments    = int(self.input_segments.text())
        s.compactness     = float(self.input_compactness.text().replace(",", "."))
        s.sigma_slic      = int(self.input_sigma.text())
        s.max_num_iter    = int(self.input_max_iter.text())
        s.min_size_factor = float(self.input_min_size.text().replace(",", "."))
        s.max_size_factor = float(self.input_max_size.text().replace(",", "."))
        s.clip_limit      = float(self.input_clip_limit.text().replace(",", "."))
        s.nbins           = int(self.input_nbins.text())
        s.multiplicator   = float(self.input_multiplier.text().replace(",", "."))
        self.accept()
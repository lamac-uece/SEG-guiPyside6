from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QHBoxLayout,
    QLabel, QLineEdit, QVBoxLayout,
)
from PySide6.QtGui import QColor, QIcon, QIntValidator, QPixmap
from src.models.segmentation_state import SegmentationState
from src.models.mesh_config import MESH_COLORS, MESH_MODES, MESH_OPACITIES

class ParamsDialog(QDialog):
    """Dialog de configuração de parâmetros SLIC, CLAHE e remoção de pele."""

    def __init__(self, state: SegmentationState, parent=None):
        super().__init__(parent)
        self._state = state
        self.setWindowTitle("Parameters")
        self._build_ui()

    def _build_ui(self):
        s = self._state

        # ── Labels de seção ───────────────────────────────────────────
        lbl_superpixel = QLabel("<h1>Superpixel</h1>")
        lbl_clahe      = QLabel("<h1>Clahe</h1>")
        lbl_skin       = QLabel("<h1>Skin Segmentation</h1>")
        lbl_mesh       = QLabel("<h1>SuperPixel Mesh</h1>")

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

        # ── Campos Malha do SuperPixel ───────────────────────────────────
        self.input_mesh_color = QComboBox()
        for name, rgb in MESH_COLORS.items():
            swatch = QPixmap(16, 16)
            swatch.fill(QColor(
                int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255)
            ))
            self.input_mesh_color.addItem(QIcon(swatch), name, rgb)
        current_color = next(
            (name for name, rgb in MESH_COLORS.items()
             if tuple(rgb) == tuple(s.mesh_color)),
            None
        )
        if current_color is not None:
            self.input_mesh_color.setCurrentText(current_color)

        self.input_mesh_mode = QComboBox()
        for label, mode in MESH_MODES.items():
            self.input_mesh_mode.addItem(label, mode)
        current_mode = next(
            (label for label, mode in MESH_MODES.items() if mode == s.mesh_mode),
            None
        )
        if current_mode is not None:
            self.input_mesh_mode.setCurrentText(current_mode)

        self.input_mesh_opacity = QComboBox()
        self.input_mesh_opacity.setEditable(True)
        self.input_mesh_opacity.setInsertPolicy(QComboBox.NoInsert)
        self.input_mesh_opacity.setToolTip(
            "Choose a preset value or type a custom percentage "
            "(e.g., 60%) to test other transparency levels."
        )
        for label, value in MESH_OPACITIES.items():
            self.input_mesh_opacity.addItem(label, value)
        current_opacity = next(
            (label for label, value in MESH_OPACITIES.items()
             if abs(value - s.mesh_opacity) < 1e-6),
            f"{round(s.mesh_opacity * 100)}%"
        )
        opacity_idx = self.input_mesh_opacity.findText(current_opacity)
        if opacity_idx >= 0:
            self.input_mesh_opacity.setCurrentIndex(opacity_idx)
        else:
            self.input_mesh_opacity.setEditText(current_opacity)

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
        layout.addWidget(lbl_mesh)
        layout.addLayout(row("Mesh Color",                  self.input_mesh_color))
        layout.addLayout(row("Mesh Thickness",              self.input_mesh_mode))
        layout.addLayout(row("Opacity",                     self.input_mesh_opacity))
        layout.addWidget(buttons)
        self.setLayout(layout)
    def _parse_opacity(self) -> float:
        """Aceita tanto os itens pré-definidos quanto um valor digitado
        livremente pelo usuário (ex.: '60%', '60' ou '0.6').
        """
        combo = self.input_mesh_opacity
        idx   = combo.currentIndex()
        text  = combo.currentText().strip()
        if idx >= 0 and combo.itemText(idx) == text:
            return float(combo.itemData(idx))

        cleaned = text.replace("%", "").replace(",", ".").strip()
        try:
            value = float(cleaned)
        except ValueError:
            return 1.0
        if value > 1.0:  # ex.: usuário digitou "60" querendo dizer 60%
            value /= 100.0
        return min(max(value, 0.0), 1.0)

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
        s.mesh_color      = self.input_mesh_color.currentData()
        s.mesh_mode       = self.input_mesh_mode.currentData()
        s.mesh_opacity    = self._parse_opacity()
        self.accept()
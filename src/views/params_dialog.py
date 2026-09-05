from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)
from PySide6.QtGui import QColor, QIcon, QIntValidator, QPixmap
from src.models.segmentation_state import SegmentationState
from src.models.mesh_config import MESH_COLORS, MESH_MODES, MESH_OPACITIES


class OptionsPanel(QWidget):
    """Painel de Options que sobrepõe o painel direito (abas) na nova UI.

    Substitui o antigo `ParamsDialog` modal por um painel embutido na mesma
    área da tela. Mantém os mesmos campos (SLIC, CLAHE, malha) e a mesma lógica
    de escrita no estado, devolvendo flags de alteração para a janela decidir
    se recomputa o SLIC, reaplica o CLAHE ou apenas redesenha a malha.
    """

    def __init__(self, state: SegmentationState, parent=None,
                 on_apply=None, on_cancel=None):
        super().__init__(parent)
        self._state = state
        self._on_apply = on_apply
        self._on_cancel = on_cancel
        self.slic_params_changed = False
        self.clahe_params_changed = False
        self._build_ui()

    # ── construção ──────────────────────────────────────────────────────────
    def _current_slic_params(self) -> tuple:
        s = self._state
        return (
            s.num_segments, s.sigma_slic, s.compactness,
            s.max_num_iter, s.min_size_factor, s.max_size_factor,
        )

    def _current_clahe_params(self) -> tuple:
        s = self._state
        return (s.clip_limit, s.nbins)

    def _build_ui(self):
        s = self._state

        def section(title):
            lbl = QLabel(f"<h3>{title}</h3>")
            lbl.setStyleSheet("margin-top: 4px;")
            return lbl

        def row(label_text, widget):
            h = QHBoxLayout()
            h.addWidget(QLabel(label_text))
            h.addWidget(widget)
            return h

        self.input_segments = QLineEdit(str(s.num_segments))
        self.input_segments.setValidator(QIntValidator(1000, 10000))

        self.input_compactness = QDoubleSpinBox()
        self.input_compactness.setValue(s.compactness)
        self.input_compactness.setMaximum(100)

        self.input_sigma = QLineEdit(str(s.sigma_slic))
        self.input_sigma.setValidator(QIntValidator(0, 10))

        self.input_max_iter = QLineEdit(str(s.max_num_iter))
        self.input_max_iter.setValidator(QIntValidator(1, 100))

        self.input_min_size = QDoubleSpinBox()
        self.input_min_size.setValue(s.min_size_factor)
        self.input_min_size.setMaximum(100)

        self.input_max_size = QDoubleSpinBox()
        self.input_max_size.setValue(s.max_size_factor)
        self.input_max_size.setMaximum(100)

        self.input_clip_limit = QDoubleSpinBox()
        self.input_clip_limit.setValue(s.clip_limit)
        self.input_clip_limit.setMaximum(10)

        self.input_nbins = QLineEdit(str(s.nbins))
        self.input_nbins.setValidator(QIntValidator(0, 1024))

        self.input_multiplier = QDoubleSpinBox()
        self.input_multiplier.setValue(s.multiplicator)
        self.input_multiplier.setMaximum(3)

        self.input_mesh_color = QComboBox()
        for name, rgb in MESH_COLORS.items():
            swatch = QPixmap(16, 16)
            swatch.fill(QColor(int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255)))
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
            "Escolha um preset ou digite uma porcentagem (ex.: 60%)."
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

        apply_btn = QPushButton("OK")
        apply_btn.clicked.connect(self._on_apply)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self._on_cancel)
        btns = QHBoxLayout()
        btns.addWidget(apply_btn)
        btns.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(section("Superpixel (SLIC)"))
        layout.addLayout(row("Superpixels",    self.input_segments))
        layout.addLayout(row("Compactness",    self.input_compactness))
        layout.addLayout(row("Sigma",          self.input_sigma))
        layout.addLayout(row("max_num_iter",   self.input_max_iter))
        layout.addLayout(row("min_size_factor", self.input_min_size))
        layout.addLayout(row("max_size_factor", self.input_max_size))
        layout.addWidget(section("CLAHE"))
        layout.addLayout(row("Clip limit",     self.input_clip_limit))
        layout.addLayout(row("nbins",          self.input_nbins))
        layout.addWidget(section("Skin Segmentation"))
        layout.addLayout(row("Multiplicator",  self.input_multiplier))
        layout.addWidget(section("Malha do SuperPixel"))
        layout.addLayout(row("Cor",            self.input_mesh_color))
        layout.addLayout(row("Espessura",      self.input_mesh_mode))
        layout.addLayout(row("Opacidade",      self.input_mesh_opacity))
        layout.addLayout(btns)
        layout.addStretch(1)

    def _on_apply(self):
        if self._on_apply is not None:
            self._on_apply()

    def _on_cancel(self):
        if self._on_cancel is not None:
            self._on_cancel()

    # ── aplicação ───────────────────────────────────────────────────────────
    def _parse_opacity(self) -> float:
        combo = self.input_mesh_opacity
        idx = combo.currentIndex()
        text = combo.currentText().strip()
        if idx >= 0 and combo.itemText(idx) == text:
            return float(combo.itemData(idx))
        cleaned = text.replace("%", "").replace(",", ".").strip()
        try:
            value = float(cleaned)
        except ValueError:
            return 1.0
        if value > 1.0:
            value /= 100.0
        return min(max(value, 0.0), 1.0)

    def apply(self) -> tuple:
        """Escreve os parâmetros no estado e devolve
        (slic_changed, clahe_changed)."""
        s = self._state
        new_slic_params = (
            int(self.input_segments.text()),
            int(self.input_sigma.text()),
            float(self.input_compactness.text().replace(",", ".")),
            int(self.input_max_iter.text()),
            float(self.input_min_size.text().replace(",", ".")),
            float(self.input_max_size.text().replace(",", ".")),
        )
        new_clahe_params = (
            float(self.input_clip_limit.text().replace(",", ".")),
            int(self.input_nbins.text()),
        )
        self.slic_params_changed = new_slic_params != self._current_slic_params()
        self.clahe_params_changed = (
            new_clahe_params != self._current_clahe_params()
        )
        s.clip_limit, s.nbins = new_clahe_params
        s.num_segments    = new_slic_params[0]
        s.sigma_slic      = new_slic_params[1]
        s.compactness     = new_slic_params[2]
        s.max_num_iter    = new_slic_params[3]
        s.min_size_factor = new_slic_params[4]
        s.max_size_factor = new_slic_params[5]
        s.multiplicator   = float(self.input_multiplier.text().replace(",", "."))
        s.mesh_color      = self.input_mesh_color.currentData()
        s.mesh_mode       = self.input_mesh_mode.currentData()
        s.mesh_opacity    = self._parse_opacity()
        return (self.slic_params_changed, self.clahe_params_changed)

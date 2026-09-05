from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QColorDialog, QHBoxLayout, QLabel, QPushButton,
    QToolButton, QVBoxLayout, QWidget,
)

from src.models.tissue_config import (
    DEFAULT_TISSUES,
    DEFAULT_TISSUE_COLORS,
    FALLBACK_COLOR,
    dictTissues,
)


def _color_icon(rgb) -> QIcon:
    pix = QPixmap(16, 16)
    pix.fill(QColor(int(rgb[0]), int(rgb[1]), int(rgb[2])))
    return QIcon(pix)


class TissuePalette(QWidget):
    """Lista vertical de tecidos para a aba Segmentação (painel direito).

    Mantém a mesma regra de habilitação da antiga `TissuePalette` horizontal:
    só fica habilitada enquanto o SuperPixel estiver ativo (`superpixel_auth`).
    Também expõe o "Tecido atual" em destaque e o botão para trocar a cor do
    tecido selecionado.
    """

    def __init__(self, parent=None, on_select=None, on_color_change=None):
        super().__init__(parent)
        self._on_select = on_select
        self._on_color_change = on_color_change

        self._header = QLabel("Segmentação")
        self._header.setStyleSheet("font-weight: bold; font-size: 13px;")

        self.current_tissue_label = QLabel("None")
        self.current_tissue_label.setStyleSheet("font-weight: bold;")

        self.color_button = QToolButton(self)
        self.color_button.setText("Trocar cor…")
        self.color_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.color_button.setIcon(_color_icon([200, 200, 200]))
        self.color_button.setEnabled(False)
        self.color_button.clicked.connect(self._on_change_color)

        current_row = QHBoxLayout()
        current_row.addWidget(QLabel("Tecido atual:"))
        current_row.addWidget(self.current_tissue_label, 1)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons = {}
        for name in DEFAULT_TISSUES:
            btn = QToolButton(self)
            btn.setText(name)
            btn.setCheckable(True)
            btn.setIcon(_color_icon(DEFAULT_TISSUE_COLORS.get(name, FALLBACK_COLOR)))
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setAutoRaise(True)
            btn.clicked.connect(lambda checked=False, n=name: self._select(n))
            self._group.addButton(btn)
            self._buttons[name] = btn

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self._header)
        layout.addLayout(current_row)
        row = QHBoxLayout()
        row.addWidget(self.color_button)
        layout.addLayout(row)
        layout.addSpacing(6)
        for name in DEFAULT_TISSUES:
            layout.addWidget(self._buttons[name])
        layout.addStretch(1)

    def _select(self, name: str) -> None:
        if self._on_select is not None:
            self._on_select(name)

    def _on_change_color(self) -> None:
        color = QColorDialog.getColor(Qt.black, self)
        qc = QColor(color)
        if qc.red() == 0 and qc.green() == 0 and qc.blue() == 0:
            return
        if self._on_color_change is not None:
            self._on_color_change(qc)

    @staticmethod
    def _entry_index(state, name: str):
        try:
            return state.informacoes["tissue"].index(dictTissues[name])
        except ValueError:
            return None

    def set_current_color(self, rgb) -> None:
        self.color_button.setIcon(_color_icon(rgb))
        self.color_button.setEnabled(True)

    def refresh(self, state) -> None:
        """Atualiza cor, destaque e habilitação de cada tecido conforme o estado."""
        enabled = bool(state.superpixel_auth)
        for name, btn in self._buttons.items():
            btn.setEnabled(enabled)
            idx = self._entry_index(state, name)
            if idx is None:
                rgb = DEFAULT_TISSUE_COLORS.get(name, FALLBACK_COLOR)
            else:
                rgb = state.informacoes["colors"][idx]
            btn.setIcon(_color_icon(rgb))
            checked = (
                idx is not None
                and state.current_tissue == idx + 1
            )
            if btn.isChecked() != checked:
                btn.setChecked(checked)

        # atualiza o destaque do tecido atual e o botão de cor
        if state.current_tissue == 0 or not state.informacoes["tissue"]:
            self.current_tissue_label.setText("None")
            self.color_button.setEnabled(False)
            self.color_button.setIcon(_color_icon([200, 200, 200]))
        else:
            idx = state.current_tissue - 1
            name = next(
                (k for k, v in dictTissues.items()
                 if v == state.informacoes["tissue"][idx]),
                None
            )
            if name is not None:
                self.current_tissue_label.setText(name)
            color = state.informacoes["colors"][idx]
            self.color_button.setIcon(_color_icon(color))
            self.color_button.setEnabled(True)

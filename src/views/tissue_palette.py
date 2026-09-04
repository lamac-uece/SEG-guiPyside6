from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPixmap
from PySide6.QtWidgets import QToolBar

from src.models.tissue_config import (
    DEFAULT_TISSUES,
    DEFAULT_TISSUE_COLORS,
    FALLBACK_COLOR,
    dictTissues,
)


class TissuePalette(QToolBar):
    """Faixa horizontal com os tecidos padrão para escolher o tecido a pintar.

    Só fica habilitada enquanto o SuperPixel estiver ativo para pintura
    (state.superpixel_auth == True), refletindo a mesma condição que libera
    o clique de pintura no canvas.
    """

    def __init__(self, parent=None, on_select=None):
        super().__init__("Tissues", parent)
        self._on_select = on_select
        self.setObjectName("TissuePalette")
        self.setMovable(False)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self._group = QActionGroup(self)
        self._group.setExclusive(True)
        self._actions = {}
        for name in DEFAULT_TISSUES:
            action = QAction(name, self)
            action.setCheckable(True)
            action.setToolTip(name)
            action.triggered.connect(
                lambda checked=False, n=name: self._select(n)
            )
            self._group.addAction(action)
            self.addAction(action)
            self._actions[name] = action

    def _select(self, name: str) -> None:
        if self._on_select is not None:
            self._on_select(name)

    @staticmethod
    def _entry_index(state, name: str):
        try:
            return state.informacoes["tissue"].index(dictTissues[name])
        except ValueError:
            return None

    def _make_icon(self, rgb) -> QIcon:
        pix = QPixmap(20, 20)
        pix.fill(QColor(int(rgb[0]), int(rgb[1]), int(rgb[2])))
        return QIcon(pix)

    def refresh(self, state) -> None:
        """Atualiza cor, destaque e habilitação de cada tecido conforme o estado."""
        enabled = bool(state.superpixel_auth)
        for name, action in self._actions.items():
            action.setEnabled(enabled)
            idx = self._entry_index(state, name)
            if idx is None:
                rgb = DEFAULT_TISSUE_COLORS.get(name, FALLBACK_COLOR)
            else:
                rgb = state.informacoes["colors"][idx]
            action.setIcon(self._make_icon(rgb))
            checked = (
                idx is not None
                and state.current_tissue == idx + 1
            )
            if action.isChecked() != checked:
                action.setChecked(checked)

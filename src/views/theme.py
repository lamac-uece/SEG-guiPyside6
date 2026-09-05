from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication


def is_dark() -> bool:
    """Detecta se o tema atual (seguindo o SO) é escuro ou claro."""
    app = QApplication.instance()
    if app is None:
        return False
    window = app.palette().window().color()
    return window.lightness() < 128


def window_color() -> QColor:
    app = QApplication.instance()
    if app is None:
        return QColor(240, 240, 240)
    return app.palette().window().color()


def canvas_face() -> QColor:
    """Fundo do canvas: neutro escuro no modo escuro, claro no claro."""
    base = window_color()
    if is_dark():
        return QColor(46, 48, 52)
    return QColor(236, 238, 242)


def axes_face() -> QColor:
    base = window_color()
    if is_dark():
        return QColor(30, 31, 34)
    return QColor(250, 250, 250)


def text_color() -> str:
    return "#e6e6e6" if is_dark() else "#1a1a1a"


def axes_edge() -> str:
    return "#555a61" if is_dark() else "#b0b6bd"


def apply_canvas_theme(fig) -> None:
    """Aplica o tema do sistema operacional ao Figure e seus eixos."""
    fig.patch.set_facecolor(canvas_face().name())
    for ax in fig.axes:
        ax.set_facecolor(axes_face().name())
        ax.tick_params(colors=text_color())
        for spine in ax.spines.values():
            spine.set_color(axes_edge())
        if ax.title.get_text():
            ax.title.set_color(text_color())
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_color(text_color())

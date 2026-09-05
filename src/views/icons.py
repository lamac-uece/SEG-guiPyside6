"""Geração de ícones simples para o rail de ferramentas da nova UI.

Os ícones são desenhados programaticamente (sem depender de assets externos),
mantendo a interface autocontida. São formas geométricas simples que
identificam cada ferramenta/ação.
"""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from src.views.theme import text_color

_ICON = 28


def _pixmap() -> QPixmap:
    pm = QPixmap(_ICON, _ICON)
    pm.fill(Qt.transparent)
    return pm


def _fg() -> QColor:
    return QColor(text_color())


def _draw(fn) -> QIcon:
    pm = _pixmap()
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    fn(p)
    p.end()
    return QIcon(pm)


def _brush(p: QPainter) -> None:
    p.setPen(QPen(QColor("#9aa0a6"), 3, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(6, 23), QPointF(18, 11))
    p.setBrush(QColor("#f2b705"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(19, 9), 5, 5)


def _eraser(p: QPainter) -> None:
    p.setBrush(QColor("#e0574f"))
    p.setPen(Qt.NoPen)
    pts = [QPointF(4, 17), QPointF(11, 24), QPointF(23, 12), QPointF(16, 5)]
    path = QPainterPath()
    path.moveTo(pts[0])
    for pt in pts[1:]:
        path.lineTo(pt)
    path.closeSubpath()
    p.drawPath(path)
    p.setBrush(QColor("#43464b"))
    p.drawRect(4, 20, 12, 4)


def _wand(p: QPainter) -> None:
    p.setPen(QPen(QColor("#9aa0a6"), 2, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(8, 24), QPointF(20, 6))
    p.setBrush(QColor("#e6e6e6"))
    p.setPen(Qt.NoPen)
    star = [
        (14, 3), (16, 8), (21, 10), (16, 12),
        (14, 17), (12, 12), (7, 10), (12, 8),
    ]
    path = QPainterPath()
    path.moveTo(*star[0])
    for x, y in star[1:]:
        path.lineTo(x, y)
    path.closeSubpath()
    p.drawPath(path)


def _restore(p: QPainter) -> None:
    p.setBrush(QColor("#9aa0a6"))
    p.setPen(Qt.NoPen)
    arrow = [QPointF(5, 13), QPointF(13, 6), QPointF(13, 10),
             QPointF(18, 10), QPointF(18, 16), QPointF(13, 16), QPointF(13, 20)]
    path = QPainterPath()
    path.moveTo(arrow[0])
    for pt in arrow[1:]:
        path.lineTo(pt)
    path.closeSubpath()
    p.drawPath(path)


def _sliders(p: QPainter) -> None:
    p.setPen(QPen(QColor("#9aa0a6"), 3, Qt.SolidLine, Qt.RoundCap))
    for y in (7, 14, 21):
        p.drawLine(QPointF(5, y), QPointF(23, y))
    p.setBrush(QColor("#f2b705"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(9, 7), 3, 3)
    p.drawEllipse(QPointF(18, 14), 3, 3)
    p.drawEllipse(QPointF(8, 21), 3, 3)


def _bolt(p: QPainter) -> None:
    p.setBrush(QColor("#f2b705"))
    p.setPen(Qt.NoPen)
    path = QPainterPath()
    path.moveTo(15, 2)
    path.lineTo(6, 15)
    path.lineTo(12, 15)
    path.lineTo(10, 26)
    path.lineTo(22, 12)
    path.lineTo(15, 12)
    path.closeSubpath()
    p.drawPath(path)


def _clahe(p: QPainter) -> None:
    p.setPen(QPen(_fg(), 2, Qt.SolidLine, Qt.RoundCap))
    for i, y in enumerate((5, 14, 23)):
        p.drawLine(QPointF(4, y), QPointF(24, y))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#f2b705"))
    p.drawRect(6 + i * 0, 5, 8, 6)
    p.setBrush(QColor("#4d90fe"))
    p.drawRect(18, 14, 6, 6)
    p.setBrush(QColor("#5cb85c"))
    p.drawRect(10, 23, 8, 4)


def _gear(p: QPainter) -> None:
    p.setPen(QPen(QColor("#9aa0a6"), 3, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    center = QPointF(14, 14)
    for i in range(8):
        ang = i * 45
        import math
        rad = math.radians(ang)
        x1 = center.x() + math.cos(rad) * 6
        y1 = center.y() + math.sin(rad) * 6
        x2 = center.x() + math.cos(rad) * 11
        y2 = center.y() + math.sin(rad) * 11
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    p.setBrush(QColor("#9aa0a6"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(center, 6, 6)
    p.setBrush(QColor(window_bg()))
    p.drawEllipse(center, 3, 3)


def _save(p: QPainter) -> None:
    p.setBrush(QColor("#5b8def"))
    p.setPen(QPen(QColor("#3b5fae"), 2))
    p.drawRoundedRect(4, 4, 20, 20, 2, 2)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor("#dfe7f5"), 2))
    p.drawLine(QPointF(8, 6), QPointF(18, 6))
    p.setBrush(QColor("#dfe7f5"))
    p.setPen(Qt.NoPen)
    p.drawRect(7, 12, 14, 8)


def _undo(p: QPainter) -> None:
    p.setPen(QPen(QColor("#9aa0a6"), 3, Qt.SolidLine, Qt.RoundCap))
    p.drawArc(6, 8, 12, 12, 0 * 16, -270 * 16)
    arrow = QPainterPath()
    arrow.moveTo(6, 8)
    arrow.lineTo(12, 4)
    arrow.lineTo(13, 9)
    arrow.closeSubpath()
    p.fillPath(arrow, QColor("#9aa0a6"))


def _open(p: QPainter) -> None:
    p.setPen(QPen(QColor("#9aa0a6"), 2))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(4, 9, 20, 14, 2, 2)
    p.drawLine(QPointF(4, 13), QPointF(24, 13))


def window_bg() -> QColor:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        return QColor(240, 240, 240)
    return app.palette().window().color()


_FUNCS = {
    "brush": _brush,
    "eraser": _eraser,
    "wand": _wand,
    "restore": _restore,
    "options": _sliders,
    "superpixel": _bolt,
    "clahe": _clahe,
    "gear": _gear,
    "save": _save,
    "undo": _undo,
    "open": _open,
}


def make_icon(name: str) -> QIcon:
    fn = _FUNCS.get(name)
    if fn is None:
        return QIcon()
    return _draw(fn)

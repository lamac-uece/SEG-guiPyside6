import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvas
from PySide6.QtWidgets import QWidget, QVBoxLayout

from src.models.segmentation_state import SegmentationState
from src.models.tissue_config import dictTissues
from src.views.theme import apply_canvas_theme


class PercentagesGraph(QWidget):
    def __init__(self, state: SegmentationState):
        super().__init__()
        self._state = state
        self.view = FigureCanvas(Figure(figsize=(5, 4)))
        apply_canvas_theme(self.view.figure)
        self.axes = self.view.figure.subplots()
        self.axes.set_title("Tissues/percentages")
        apply_canvas_theme(self.view.figure)
        vlayout = QVBoxLayout(self)
        vlayout.setContentsMargins(0, 0, 0, 0)
        vlayout.addWidget(self.view)
        self.setLayout(vlayout)

    def clear(self):
        self.axes.clear()
        self.axes.set_title("Tissues/percentages")
        self.axes.text(
            0.5, 0.5, "Sem máscara para calcular\n(Aplique o SuperPixel e pinte)",
            ha="center", va="center", transform=self.axes.transAxes
        )
        apply_canvas_theme(self.view.figure)
        self.view.draw()

    def calculatePercentages(self):
        s = self._state
        if np.array_equal(s.mask3d, []) or np.array_equal(s.segmented_mask, []):
            self.clear()
            return

        list_keys   = list(dictTissues.keys())
        list_values = list(dictTissues.values())
        total_pixels = s.area
        labels, sizes, colors = [], [], []

        for i in range(len(s.informacoes["tissue"])):
            tissue     = s.informacoes["tissue"][i]
            identifier = s.informacoes["identifier"][i]
            labels.append(list_keys[list_values.index(tissue)])
            pixels = int(np.count_nonzero(s.segmented_mask == identifier))
            total_pixels -= pixels
            sizes.append(pixels)
            c = s.informacoes["colors"][i]
            colors.append([c[0] / 255, c[1] / 255, c[2] / 255])

        sizes.append(max(total_pixels, 0))
        labels.append("Unsegmented")
        colors.append([50 / 255, 50 / 255, 50 / 255])

        total = sum(sizes)
        sizes = [100 * x / total if total else 0.0 for x in sizes]
        x_labels = [f"{labels[i]}\n{round(sizes[i], 2)}%" for i in range(len(sizes))]
        x = np.arange(len(sizes))

        self.axes.clear()
        self.axes.set_title("Tissues/percentages")
        self.axes.bar(x, sizes, color=colors, linewidth=0.2, edgecolor=[0, 0, 0])
        self.axes.set_xticks(x)
        self.axes.set_xticklabels(x_labels)
        self.axes.set_xlabel("Tissues")
        self.axes.set_ylabel("Percentages")
        apply_canvas_theme(self.view.figure)
        self.view.draw()

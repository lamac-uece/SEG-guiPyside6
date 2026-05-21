from collections import namedtuple
from os import path

import numpy as np
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
import matplotlib.backends.backend_qt5 as backend
from PySide6.QtWidgets import QFileDialog

from src.models.segmentation_state import SegmentationState
from src.services.mask_io import save_mask
from src.utils.modes import _Mode


class MplToolbar(NavigationToolbar2QT):
    def __init__(self, canvas_, parent_, plot: int, state: SegmentationState):
        backend.figureoptions = None
        self.toolitems = (
            ('Home', 'Reset original view', 'home', 'home'),
            ('Back', 'Back to previous view', 'back', 'back'),
            ('Forward', 'Forward to next view', 'forward', 'forward'),
            (None, None, None, None),
            ('Pan', 'Pan axes with left mouse, zoom with right', 'move', 'pan'),
            ('Zoom', 'Zoom to rectangle', 'zoom_to_rect', 'zoom'),
            ('Port', 'Back to the previous paint', 'back', 'back_paint'),
            ('Clear', 'Undo an specific paint', path.realpath(path.curdir) + "/trash", 'change_undo'),
            ('Save', 'Save the current image', 'filesave', 'save_mask'),
        )
        NavigationToolbar2QT.__init__(self, canvas_, parent_)
        self._actions['change_undo'].setCheckable(True)
        self.undo = False
        self.plot = plot
        self._state = state

    def _update_buttons_checked(self):
        if 'change_undo' in self._actions:
            self._actions['change_undo'].setChecked(self.undo)
        if 'pan' in self._actions:
            self._actions['pan'].setChecked(self.mode.name == 'PAN')
        if 'zoom' in self._actions:
            self._actions['zoom'].setChecked(self.mode.name == 'ZOOM')

    def change_undo(self):
        self.undo = not self.undo
        s = self._state
        if self.undo:
            if self.plot == 1 and s.undo == 0:
                s.undo = 1
            elif self.plot == 2 and s.undo == 0:
                s.undo = 2
            else:
                s.undo = 3
        else:
            if self.plot == 1 and s.undo == 1:
                s.undo = 0
            elif self.plot == 2 and s.undo == 2:
                s.undo = 0
            elif self.plot == 1 and s.undo == 3:
                s.undo = 2
            else:
                s.undo = 1

        if self.mode == _Mode.CLEAR:
            self.mode = _Mode.NONE
            self.canvas.widgetlock.release(self)
        else:
            self.mode = _Mode.CLEAR
            self.canvas.widgetlock(self)
        for a in self.canvas.figure.get_axes():
            a.set_navigate_mode(self.mode._navigate_mode)
        self.set_message(self.mode)
        _ZoomInfo = namedtuple("_ZoomInfo", "direction start_xy axes cid cbar")  
        self._update_buttons_checked()

    def save_mask(self):
        """Salva a máscara segmentada em .csv."""
        s = self._state
        if np.array_equal(s.segmented_mask, []):
            return
        from PySide6.QtCore import QDir
        a = QDir()
        if path.exists("./defaultMaskDir.txt"):
            a.setPath(s.save_dir)
        else:
            a.setPath(QDir.currentPath())
        suggested = path.basename(s.file_name_global).split(".")[0] + ".csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save File", f"{a.path()}/{suggested}", filter="csv(*.csv)"
        )
        if file_path:
            # service para salvar máscara segmentada
            save_mask(file_path, s.segmented_mask, s.informacoes, s.area)

    def back_paint(self):
        """Desfaz a última pintura."""
        import copy
        s = self._state
        if len(s.previous_paints) < 1:
            return
        s.mask3d = copy.deepcopy(s.previous_paints[-1])
        s.previous_paints.pop()
        last = len(s.previous_segments["superpixel"]) - 1
        s.segmented_mask[
            s.segments_global == s.previous_segments["superpixel"][last]
        ] = s.previous_segments["previous_identifier"][last]
        s.previous_segments["superpixel"].pop(last)
        s.previous_segments["previous_identifier"].pop(last)
        self._refresh_view(s)

    def _refresh_view(self, s: SegmentationState):
        """Aciona a atualização visual correta após back_paint."""
        # Será substituído por sinal do controller na Fase 4b
        parent = self.parent()
        if hasattr(parent, 'UpdateView'):
            if np.array_equal(s.segments_global, []) and not np.array_equal(s.mask3d, []):
                parent.showSavedMask()
            else:
                parent.UpdateView()
from collections import namedtuple
from os import path

from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
import matplotlib.backends.backend_qt5 as backend

from src.models.segmentation_state import SegmentationState
from src.utils.modes import _Mode

class MplToolbar(NavigationToolbar2QT):
    """
    Toolbar matplotlib estendida.
    back_paint e save_mask são delegados ao controller via callback,
    evitando que a view acesse services diretamente.
    """

    def __init__(self, canvas_, parent_, plot: int, state: SegmentationState,
                 on_back_paint=None, on_save_mask=None):
        backend.figureoptions = None
        self.toolitems = (
            ('Home',    'Reset original view',                   'home',                              'home'),
            ('Back',    'Back to previous view',                 'back',                              'back'),
            ('Forward', 'Forward to next view',                  'forward',                           'forward'),
            (None, None, None, None),
            ('Pan',     'Pan axes with left mouse, zoom with right', 'move',                          'pan'),
            ('Zoom',    'Zoom to rectangle',                     'zoom_to_rect',                      'zoom'),
            ('Port',    'Back to the previous paint',            'back',                              'back_paint'),
            ('Clear',   'Undo a specific paint',                 path.join(path.realpath(path.curdir), "assets", "trash"), 'change_undo'),
            ('Save',    'Save the current image',                'filesave',                          'save_mask'),
        )
        NavigationToolbar2QT.__init__(self, canvas_, parent_)
        self._actions['change_undo'].setCheckable(True)
        self.undo            = False
        self.plot            = plot
        self._state          = state
        self._on_back_paint  = on_back_paint
        self._on_save_mask   = on_save_mask

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
        _ZoomInfo = namedtuple("_ZoomInfo", "direction start_xy axes cid cbar")  # noqa: F841
        self._update_buttons_checked()

    def back_paint(self):
        """Delega ao controller via callback."""
        if self._on_back_paint:
            self._on_back_paint()

    def save_mask(self):
        """Delega ao controller via callback."""
        if self._on_save_mask:
            self._on_save_mask()
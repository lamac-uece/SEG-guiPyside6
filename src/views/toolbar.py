from collections import namedtuple

from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
import matplotlib.backends.backend_qt5 as backend

from src.models.segmentation_state import SegmentationState
from src.utils.modes import _Mode

class MplToolbar(NavigationToolbar2QT):
    """
    Toolbar matplotlib do canvas único: mantém apenas navegação de view
    (Home/Back/Forward) e Pan/Zoom. Pintura, borracha, undo e salvar são
    expostos pela nova UI (rail/topbar), não mais por botões deste toolbar.
    """

    def __init__(self, canvas_, parent_, plot: int, state: SegmentationState):
        backend.figureoptions = None
        self.toolitems = (
            ('Home',    'Reset original view',                   'home',                              'home'),
            ('Back',    'Back to previous view',                 'back',                              'back'),
            ('Forward', 'Forward to next view',                  'forward',                           'forward'),
            (None, None, None, None),
            ('Pan',     'Pan axes with left mouse, zoom with right', 'move',                          'pan'),
            ('Zoom',    'Zoom to rectangle',                     'zoom_to_rect',                      'zoom'),
        )
        NavigationToolbar2QT.__init__(self, canvas_, parent_)
        self.undo            = False
        self.plot            = plot
        self._state          = state

    def _update_buttons_checked(self):
        if 'pan' in self._actions:
            self._actions['pan'].setChecked(self.mode.name == 'PAN')
        if 'zoom' in self._actions:
            self._actions['zoom'].setChecked(self.mode.name == 'ZOOM')

    def change_undo(self):
        """Liga/desliga o modo de apagar (mesma lógica da antiga ferramenta
        Clear do toolbar matplotlib). Com um canvas único, plot == 1."""
        s = self._state
        if self.undo:
            self.undo = False
            s.undo = 0
        else:
            self.undo = True
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

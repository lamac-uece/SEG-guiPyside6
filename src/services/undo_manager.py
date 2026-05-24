import copy
from dataclasses import dataclass, field
import numpy as np

MAX_HISTORY = 10

@dataclass
class UndoEntry:
    mask3d_snapshot: np.ndarray
    segment_id: int
    previous_identifier: int

class UndoStack:
    """
    Encapsula o histórico de pinturas para suporte ao ctrl+z.
    Mantém no máximo MAX_HISTORY entradas
    """
    def __init__(self):
        self._entries: list[UndoEntry] = []

    def push(self, mask3d: np.ndarray, segment_id: int, previous_identifier: int):
        """Salva o estado atual da máscara 3D antes de uma nova pintura."""
        entry = UndoEntry(
            mask3d_snapshot=copy.deepcopy(mask3d),
            segment_id=segment_id,
            previous_identifier=previous_identifier
        )
        self._entries.append(entry)
        if len(self._entries) > MAX_HISTORY:
            self._entries.pop(0)
    
    def pop(self):
        """Remove e retorna o último estado salvo. Retorna None se não houver histórico."""
        if not self._entries:
            return None
        return self._entries.pop()
    
    def clear(self):
        """Limpa todo o histórico de undo."""
        self._entries.clear()
    
    def __len__(self):
        """Retorna o número de entradas no histórico."""
        return len(self._entries)

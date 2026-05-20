from enum import Enum

class _Mode(str, Enum):
    NONE = ""
    CLEAR = "clear"

    def __str__(self):
        return self.value
    
    @property
    def _navigate_mode(self):
        return self.name if self is not _Mode.NONE else None
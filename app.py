import sys
import pydicom
import pydicom.pixel_data_handlers.pylibjpeg_handler
from PySide6.QtWidgets import QApplication
from src.models.segmentation_state import SegmentationState
from src.controllers.main_controller import MainController
from src.views.main_window import ImageViewer

if __name__ == '__main__':
    app        = QApplication(sys.argv)
    state      = SegmentationState()
    controller = MainController(state)
    viewer     = ImageViewer(state, controller)
    viewer.show()
    sys.exit(app.exec())
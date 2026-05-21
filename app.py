# app.py
import sys
import pydicom  # necessário para os handlers internos do pydicom
import pydicom.pixel_data_handlers.pylibjpeg_handler  # handler JPEG lossless
from PySide6.QtWidgets import QApplication
from src.models.segmentation_state import SegmentationState
from src.views.main_window import ImageViewer

if __name__ == '__main__':
    app = QApplication(sys.argv)
    state = SegmentationState()
    viewer = ImageViewer(state)
    viewer.show()
    sys.exit(app.exec())
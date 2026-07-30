import sys
import pydicom
import pydicom.pixel_data_handlers.pylibjpeg_handler
from PySide6.QtWidgets import QApplication, QMessageBox
from src.models.segmentation_state import SegmentationState
from src.controllers.main_controller import MainController
from src.views.main_window import ImageViewer
from src.services import ml_segmentation

if __name__ == '__main__':
    app        = QApplication(sys.argv)
    state      = SegmentationState()
    controller = MainController(state)
    viewer     = ImageViewer(state, controller)

    failures = ml_segmentation.load_all_models()
    if failures:
        detalhes = "\n".join(f"- {tissue}: {motivo}" for tissue, motivo in failures)
        QMessageBox.warning(
            viewer, "Aviso",
            "Alguns modelos de segmentação automática não puderam ser carregados:\n\n"
            f"{detalhes}\n\n"
            "Os tecidos afetados ficarão indisponíveis para segmentação automática, "
            "mas a segmentação manual segue funcionando normalmente."
        )

    viewer.show()
    sys.exit(app.exec())
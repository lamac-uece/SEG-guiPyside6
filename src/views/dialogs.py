from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QLabel
from PySide6.QtGui import QPixmap

class CustomDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LAMAC")
        self.setWindowIcon(QPixmap("./icon.png"))

        QBtn = QDialogButtonBox.Yes | QDialogButtonBox.No
        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        layout = QVBoxLayout()
        message = QLabel(
            "<center>Deseja aproveitar a mascara</center>\n"
            "<center>do arquivo .csv atual?</center>"
        )
        layout.addWidget(message)
        layout.addWidget(self.buttonBox)
        self.setLayout(layout)

    def show(self) -> bool:
        return self.exec()
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)
from PySide6.QtGui import QPixmap

class CustomDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LAMAC")
        self.setWindowIcon(QPixmap("assets/icon.png"))

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


class MLReviewDialog(QDialog):
    """
    Diálogo exibido logo após uma segmentação automática, com as três
    ações de revisão da proposta do modelo:

        - "Aceitar"  → incorpora o resultado ao estado de segmentação em
                        memória (não salva .csv — isso é feito à parte,
                        via File → Save, permitindo encadear outras
                        segmentações automáticas antes de salvar)
        - "Editar"   → aceita como ponto de partida e já prepara a imagem
                        para correção manual (gera os superpixels)
        - "Rejeitar" → descarta a proposta e restaura o estado anterior

    Uso:
        choice = MLReviewDialog(tissue_name).show()
        # choice é "accept", "edit", "reject" ou None (se fechado sem escolher)
    """

    def __init__(self, tissue_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LAMAC")
        self.setWindowIcon(QPixmap("assets/icon.png"))
        self._choice = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"<center>Segmentação automática de <b>{tissue_name}</b> concluída.</center>\n"
            "<center>O que deseja fazer com o resultado?</center>"
        ))

        buttons = QHBoxLayout()
        accept_btn = QPushButton("Aceitar")
        edit_btn   = QPushButton("Editar")
        reject_btn = QPushButton("Rejeitar")
        accept_btn.clicked.connect(lambda: self._select("accept"))
        edit_btn.clicked.connect(lambda: self._select("edit"))
        reject_btn.clicked.connect(lambda: self._select("reject"))
        for btn in (accept_btn, edit_btn, reject_btn):
            buttons.addWidget(btn)
        layout.addLayout(buttons)

    def _select(self, choice: str) -> None:
        self._choice = choice
        self.accept()

    def show(self) -> str | None:
        self.exec()
        return self._choice


class MLTissueSelectionDialog(QDialog):
    """
    Diálogo do modo Auto (D4): escolha de quais tecidos, dentre os
    cobertos pelo modelo multiclasse do modo Auto, aplicar nesta rodada.
    Todos vêm marcados por padrão (o modelo roda para os 4 de qualquer
    forma — isso só filtra quais propostas são de fato aplicadas/revisadas).

    Uso:
        selected = MLTissueSelectionDialog(tissues).show()
        # selected é list[str] com pelo menos 1 item, ou None (cancelado
        # ou nenhum tecido marcado)
    """

    def __init__(self, tissues: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("LAMAC")
        self.setWindowIcon(QPixmap("assets/icon.png"))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<center>Segmentação Auto — selecione os tecidos:</center>"))

        self._checkboxes: dict[str, QCheckBox] = {}
        for tissue in tissues:
            checkbox = QCheckBox(tissue)
            checkbox.setChecked(True)
            layout.addWidget(checkbox)
            self._checkboxes[tissue] = checkbox

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def show(self) -> list[str] | None:
        if self.exec() != QDialog.Accepted:
            return None
        selected = [t for t, cb in self._checkboxes.items() if cb.isChecked()]
        return selected or None
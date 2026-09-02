"""
Worker Qt genérico para rodar inferência (bloqueante) fora da thread
principal, usado pelos dois modos de segmentação automática (Semi-Auto e
Auto) — a única diferença entre eles é a função e os argumentos passados.

`fn` deve ser uma chamada pura (sem tocar em widgets/Qt): em
`main_controller.py`, `predict_ml_single`/`predict_ml_batch` só leem o
estado e chamam o serviço de ONNX — a aplicação do resultado ao estado e
à view (que mexe em widgets) roda depois, na thread principal, no slot
conectado a `finished`.
"""

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class InferenceWorker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as e:
            self.signals.failed.emit(str(e))
        else:
            self.signals.finished.emit(result)

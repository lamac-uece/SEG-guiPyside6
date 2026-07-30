# tests/unit/test_ml_segmentation.py
# importado uma única vez, no carregamento do módulo de teste — evita um
# problema específico do pytest com o import tardio de keras.src.visualization
# (que arrasta matplotlib) se disparado de dentro de uma função de teste.
import keras
import numpy as np
import pytest

from src.services import ml_segmentation
from src.services.ml_segmentation import (
    MLSegmentationError, available_tissues, is_tissue_loaded, predict_mask,
)
from src.models.ml_tissue_config import MLModelSpec


@pytest.fixture(autouse=True)
def _reset_loaded_models():
    """Garante isolamento entre testes: nenhum modelo "vaza" de um teste pro outro."""
    ml_segmentation._LOADED_MODELS.clear()
    yield
    ml_segmentation._LOADED_MODELS.clear()


# ── preprocess ──────────────────────────────────────────────────────────────

def test_preprocess_output_shape():
    img = np.random.randint(0, 255, (256, 300), dtype=np.uint8)
    result = ml_segmentation.preprocess(img, target_size=512)
    assert result.shape == (1, 512, 512, 1)

def test_preprocess_normalizes_to_unit_range():
    img = np.array([[0, 255], [128, 64]], dtype=np.uint8)
    result = ml_segmentation.preprocess(img, target_size=4)
    assert result.min() >= 0.0
    assert result.max() <= 1.0

def test_preprocess_output_dtype():
    img = np.random.randint(0, 255, (64, 64), dtype=np.uint8)
    result = ml_segmentation.preprocess(img, target_size=32)
    assert result.dtype == np.float32


# ── load_all_models: carregamento eager, isolado por tecido ─────────────────

class _FakeModel:
    """Substitui keras.models.load_model(...): devolve sempre a mesma predição."""

    def __init__(self, prediction: np.ndarray):
        self._prediction = prediction

    def predict(self, net_input, verbose=0):
        return self._prediction

def test_available_tissues_empty_before_loading():
    """Antes de load_all_models() rodar, nenhum tecido deve aparecer disponível."""
    assert available_tissues() == []

def test_load_all_models_success(monkeypatch):
    fake_registry = {"Fat": MLModelSpec(model_path="fake/fat.keras")}
    monkeypatch.setattr(ml_segmentation, "ML_TISSUE_MODELS", fake_registry)
    monkeypatch.setattr(ml_segmentation.os.path, "exists", lambda path: True)

    monkeypatch.setattr(
        keras.models, "load_model", lambda path: _FakeModel(np.zeros((1, 512, 512, 1)))
    )

    failures = ml_segmentation.load_all_models()

    assert failures == []
    assert available_tissues() == ["Fat"]
    assert is_tissue_loaded("Fat")

def test_load_all_models_isolates_failure(monkeypatch):
    """Um tecido com arquivo ausente não pode impedir os demais de carregar."""
    fake_registry = {
        "Fat":    MLModelSpec(model_path="fake/fat.keras"),
        "Muscle": MLModelSpec(model_path="fake/muscle.keras"),
    }
    monkeypatch.setattr(ml_segmentation, "ML_TISSUE_MODELS", fake_registry)
    # só "fake/fat.keras" "existe"
    monkeypatch.setattr(
        ml_segmentation.os.path, "exists", lambda path: path == "fake/fat.keras"
    )

    monkeypatch.setattr(
        keras.models, "load_model", lambda path: _FakeModel(np.zeros((1, 512, 512, 1)))
    )

    failures = ml_segmentation.load_all_models()

    failed_tissues = [tissue for tissue, _ in failures]
    assert failed_tissues == ["Muscle"]
    assert available_tissues() == ["Fat"]
    assert is_tissue_loaded("Fat")
    assert not is_tissue_loaded("Muscle")


# ── predict_mask ──────────────────────────────────────────────────────────

def test_predict_mask_shape_matches_original_image(monkeypatch):
    fake_registry = {"Fat": MLModelSpec(model_path="fake/fat.keras")}
    monkeypatch.setattr(ml_segmentation, "ML_TISSUE_MODELS", fake_registry)

    original_shape = (100, 150)
    fake_pred = np.ones((1, 512, 512, 1), dtype=np.float32)
    ml_segmentation._LOADED_MODELS["Fat"] = _FakeModel(fake_pred)

    img = np.random.randint(0, 255, original_shape, dtype=np.uint8)
    mask = predict_mask(img, "Fat")

    assert mask.shape == original_shape
    assert mask.dtype == np.bool_

def test_predict_mask_applies_threshold(monkeypatch):
    fake_registry = {"Fat": MLModelSpec(model_path="fake/fat.keras", threshold=0.5)}
    monkeypatch.setattr(ml_segmentation, "ML_TISSUE_MODELS", fake_registry)

    fake_pred = np.zeros((1, 512, 512, 1), dtype=np.float32)
    fake_pred[:, :256, :, :] = 0.9   # acima do threshold -> True
    fake_pred[:, 256:, :, :] = 0.1   # abaixo do threshold -> False
    ml_segmentation._LOADED_MODELS["Fat"] = _FakeModel(fake_pred)

    img = np.zeros((512, 512), dtype=np.uint8)
    mask = predict_mask(img, "Fat")

    assert mask[:256, :].all()
    assert not mask[256:, :].any()

def test_predict_mask_unloaded_tissue_raises():
    """Tecido nunca carregado (ou que falhou em load_all_models) deve dar erro claro."""
    with pytest.raises(MLSegmentationError):
        predict_mask(np.zeros((64, 64), dtype=np.uint8), "Fat")
import numpy as np
import pytest

from src.services import ml_segmentation
from src.services.ml_segmentation import (
    MLSegmentationError, available_tissues, is_tissue_loaded,
    predict_mask, predict_masks,
)
from src.models.ml_tissue_config import MLModelSpec


@pytest.fixture(autouse=True)
def _reset_loaded_models():
    """Garante isolamento entre testes: nenhuma sessão "vaza" de um teste pro outro."""
    ml_segmentation._LOADED_SESSIONS.clear()
    yield
    ml_segmentation._LOADED_SESSIONS.clear()


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


# ── load_all_models: carregamento eager, isolado por modelo ─────────────────

class _FakeInput:
    name = "input"

class _FakeSession:
    """Substitui onnxruntime.InferenceSession(...): devolve sempre a mesma predição."""

    def __init__(self, path, providers=None):
        self.path = path

    def get_inputs(self):
        return [_FakeInput()]

    def run(self, output_names, feed):
        raise NotImplementedError  # sobrescrito por instância nos testes que precisam


def test_available_tissues_empty_before_loading():
    """Antes de load_all_models() rodar, nenhum tecido deve aparecer disponível."""
    assert available_tissues("semi_auto") == []
    assert available_tissues("auto") == []

def test_load_all_models_success(monkeypatch):
    fake_registry = {
        "UNet-Multiclasse": MLModelSpec(
            model_path="fake/unet_all.onnx", model_type="multiclass",
            tissues=("Fat",),
        ),
    }
    monkeypatch.setattr(ml_segmentation, "ML_TISSUE_MODELS", fake_registry)
    monkeypatch.setattr(ml_segmentation, "MODE_MODEL", {"semi_auto": "UNet-Multiclasse", "auto": "UNet-Multiclasse"})
    monkeypatch.setattr(ml_segmentation.os.path, "exists", lambda path: True)
    monkeypatch.setattr(ml_segmentation.ort, "InferenceSession", _FakeSession)

    failures = ml_segmentation.load_all_models()

    assert failures == []
    assert ml_segmentation.is_model_loaded("UNet-Multiclasse")
    assert available_tissues("semi_auto") == ["Fat"]

def test_load_all_models_isolates_failure(monkeypatch):
    """Um modelo com arquivo ausente não pode impedir os demais de carregar."""
    fake_registry = {
        "UNet-Multiclasse": MLModelSpec(model_path="fake/unet_all.onnx", model_type="multiclass", tissues=("Fat",)),
        "R2-Multiclasse":   MLModelSpec(model_path="fake/r2_all.onnx",   model_type="multiclass", tissues=("Fat",)),
    }
    monkeypatch.setattr(ml_segmentation, "ML_TISSUE_MODELS", fake_registry)
    # só "fake/unet_all.onnx" "existe"
    monkeypatch.setattr(
        ml_segmentation.os.path, "exists", lambda path: path == "fake/unet_all.onnx"
    )
    monkeypatch.setattr(ml_segmentation.ort, "InferenceSession", _FakeSession)

    failures = ml_segmentation.load_all_models()

    failed_models = [model for model, _ in failures]
    assert failed_models == ["R2-Multiclasse"]
    assert ml_segmentation.is_model_loaded("UNet-Multiclasse")
    assert not ml_segmentation.is_model_loaded("R2-Multiclasse")


# ── predict_masks (multiclasse) ──────────────────────────────────────────────

def _session_with_output(output: np.ndarray) -> _FakeSession:
    session = _FakeSession("fake/model.onnx")
    session.run = lambda output_names, feed: [output]
    return session

def test_predict_masks_decodes_channels_by_tissue_order(monkeypatch):
    """Canal 0 -> primeiro tecido de `tissues`, canal 1 -> segundo, etc."""
    fake_registry = {
        "R2-Multiclasse": MLModelSpec(
            model_path="fake/r2_all.onnx", model_type="multiclass",
            tissues=("Intramuscular Fat", "Muscle", "Fat", "Visceral Fat"),
        ),
    }
    monkeypatch.setattr(ml_segmentation, "ML_TISSUE_MODELS", fake_registry)

    output = np.zeros((1, 8, 8, 4, 1), dtype=np.float32)
    output[0, :4, :, 0, 0] = 0.9   # Intramuscular Fat só na metade de cima
    output[0, :, :, 1, 0] = 0.9    # Muscle em tudo
    ml_segmentation._LOADED_SESSIONS["R2-Multiclasse"] = _session_with_output(output)

    img = np.zeros((8, 8), dtype=np.uint8)
    masks = predict_masks("R2-Multiclasse", img)

    assert set(masks) == {"Intramuscular Fat", "Muscle", "Fat", "Visceral Fat"}
    assert masks["Intramuscular Fat"][:4, :].all()
    assert not masks["Intramuscular Fat"][4:, :].any()
    assert masks["Muscle"].all()
    assert not masks["Fat"].any()
    assert not masks["Visceral Fat"].any()

def test_predict_masks_resolves_overlap_by_priority(monkeypatch):
    """Pixel ativo em 2 canais: vence o tecido de maior prioridade em conflict_priority."""
    fake_registry = {
        "R2-Multiclasse": MLModelSpec(
            model_path="fake/r2_all.onnx", model_type="multiclass",
            tissues=("Intramuscular Fat", "Muscle"),
            conflict_priority=("Muscle", "Intramuscular Fat"),
        ),
    }
    monkeypatch.setattr(ml_segmentation, "ML_TISSUE_MODELS", fake_registry)

    output = np.zeros((1, 4, 4, 2, 1), dtype=np.float32)
    output[0, :, :, 0, 0] = 0.9  # Intramuscular Fat em tudo
    output[0, :, :, 1, 0] = 0.9  # Muscle em tudo -> sobreposição total
    ml_segmentation._LOADED_SESSIONS["R2-Multiclasse"] = _session_with_output(output)

    masks = predict_masks("R2-Multiclasse", np.zeros((4, 4), dtype=np.uint8))

    assert masks["Muscle"].all()
    assert not masks["Intramuscular Fat"].any()

def test_predict_masks_shape_matches_original_image(monkeypatch):
    fake_registry = {
        "R2-Multiclasse": MLModelSpec(
            model_path="fake/r2_all.onnx", model_type="multiclass", tissues=("Fat",),
        ),
    }
    monkeypatch.setattr(ml_segmentation, "ML_TISSUE_MODELS", fake_registry)

    output = np.ones((1, 512, 512, 1, 1), dtype=np.float32)
    ml_segmentation._LOADED_SESSIONS["R2-Multiclasse"] = _session_with_output(output)

    original_shape = (100, 150)
    img = np.zeros(original_shape, dtype=np.uint8)
    masks = predict_masks("R2-Multiclasse", img)

    assert masks["Fat"].shape == original_shape
    assert masks["Fat"].dtype == np.bool_


# ── predict_mask (Semi-Auto: fallback multiclasse, 1 tecido) ────────────────

def test_predict_mask_extracts_single_channel_from_semi_auto_model(monkeypatch):
    fake_registry = {
        "UNet-Multiclasse": MLModelSpec(
            model_path="fake/unet_all.onnx", model_type="multiclass",
            tissues=("Fat", "Muscle"), threshold=0.5,
        ),
    }
    monkeypatch.setattr(ml_segmentation, "ML_TISSUE_MODELS", fake_registry)
    monkeypatch.setattr(ml_segmentation, "MODE_MODEL", {"semi_auto": "UNet-Multiclasse", "auto": "UNet-Multiclasse"})

    output = np.zeros((1, 512, 512, 2, 1), dtype=np.float32)
    output[:, :256, :, 0, :] = 0.9   # Fat acima do threshold na metade de cima
    output[:, 256:, :, 0, :] = 0.1
    ml_segmentation._LOADED_SESSIONS["UNet-Multiclasse"] = _session_with_output(output)

    mask = predict_mask(np.zeros((512, 512), dtype=np.uint8), "Fat")

    assert mask.shape == (512, 512)
    assert mask.dtype == np.bool_
    assert mask[:256, :].all()
    assert not mask[256:, :].any()

def test_predict_mask_unloaded_model_raises():
    """Modelo do modo Semi-Auto nunca carregado deve dar erro claro."""
    with pytest.raises(MLSegmentationError):
        predict_mask(np.zeros((64, 64), dtype=np.uint8), "Fat")

def test_predict_mask_tissue_not_covered_raises(monkeypatch):
    fake_registry = {
        "UNet-Multiclasse": MLModelSpec(
            model_path="fake/unet_all.onnx", model_type="multiclass", tissues=("Fat",),
        ),
    }
    monkeypatch.setattr(ml_segmentation, "ML_TISSUE_MODELS", fake_registry)
    monkeypatch.setattr(ml_segmentation, "MODE_MODEL", {"semi_auto": "UNet-Multiclasse", "auto": "UNet-Multiclasse"})
    ml_segmentation._LOADED_SESSIONS["UNet-Multiclasse"] = _session_with_output(
        np.zeros((1, 64, 64, 1, 1), dtype=np.float32)
    )

    with pytest.raises(MLSegmentationError):
        predict_mask(np.zeros((64, 64), dtype=np.uint8), "Muscle")

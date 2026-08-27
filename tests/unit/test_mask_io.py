# tests/unit/test_mask_io.py
import numpy as np
import tempfile
import os
from src.services.mask_io import save_mask, load_mask


def _fixtures():
    mask = np.zeros((10, 10), dtype=int)
    mask[3:7, 3:7] = 1
    informacoes = {
        "colors":     [np.array([255, 255, 0]), np.array([255, 0, 0])],
        "identifier": [1, 2],
        "tissue":     [3, 5]
    }
    area = 512
    return mask, informacoes, area


def _tmp():
    f = tempfile.NamedTemporaryFile(suffix='.csv', delete=False)
    f.close()
    return f.name


# ── roundtrip sintético ───────────────────────────────────────────────────────

def test_roundtrip_mask():
    mask, info, area = _fixtures()
    path = _tmp()
    try:
        save_mask(path, mask, info, area)
        loaded_mask, _, _, _ = load_mask(path)
        assert np.array_equal(mask, loaded_mask)
    finally:
        os.unlink(path)


def test_roundtrip_area():
    mask, info, area = _fixtures()
    path = _tmp()
    try:
        save_mask(path, mask, info, area)
        _, _, loaded_area, _ = load_mask(path)
        assert loaded_area == area
    finally:
        os.unlink(path)


def test_roundtrip_colors():
    mask, info, area = _fixtures()
    path = _tmp()
    try:
        save_mask(path, mask, info, area)
        _, loaded_info, _, _ = load_mask(path)
        for original, loaded in zip(info["colors"], loaded_info["colors"]):
            assert np.array_equal(original, loaded)
    finally:
        os.unlink(path)


def test_roundtrip_tissue_and_identifier():
    mask, info, area = _fixtures()
    path = _tmp()
    try:
        save_mask(path, mask, info, area)
        _, loaded_info, _, _ = load_mask(path)
        assert loaded_info["tissue"] == info["tissue"]
        assert loaded_info["identifier"] == info["identifier"]
    finally:
        os.unlink(path)


def test_roundtrip_source_id():
    """Um source_id salvo deve ser recuperado intacto ao carregar o CSV."""
    mask, info, area = _fixtures()
    path = _tmp()
    try:
        save_mask(path, mask, info, area, source_id="1.2.3.4.5")
        loaded_mask, _, loaded_area, loaded_source_id = load_mask(path)
        assert np.array_equal(mask, loaded_mask)
        assert loaded_area == area
        assert loaded_source_id == "1.2.3.4.5"
    finally:
        os.unlink(path)


def test_legacy_csv_without_source_id():
    """CSVs salvos sem source_id devem continuar sendo lidos corretamente."""
    mask, info, area = _fixtures()
    path = _tmp()
    try:
        save_mask(path, mask, info, area)
        loaded_mask, loaded_info, loaded_area, loaded_source_id = load_mask(path)
        assert np.array_equal(mask, loaded_mask)
        assert loaded_area == area
        assert loaded_source_id == ""
    finally:
        os.unlink(path)


# ── arquivo real do projeto ───────────────────────────────────────────────────

def test_load_real_csv():
    """Garante que o test.csv existente no projeto é lido sem erros."""
    real_path = "test.csv"
    if not os.path.exists(real_path):
        return

    segmented_mask, informacoes, area, _ = load_mask(real_path)

    assert isinstance(segmented_mask, np.ndarray)
    assert segmented_mask.ndim == 2
    assert area > 0
    assert len(informacoes["colors"]) > 0
    assert len(informacoes["colors"]) == len(informacoes["tissue"])
    assert len(informacoes["colors"]) == len(informacoes["identifier"])
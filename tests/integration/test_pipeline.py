import os
import tempfile
import numpy as np
import pytest
from src.services.mask_io import load_mask, save_mask
from src.services.image_processing import (
    select_RoI,
    apply_clahe,
    compute_superpixels,
)
from src.utils.image_utils import ConvertToUint8, tissue_segmentation


# ── Fluxo 2 — CSV roundtrip (não precisa de DICOM real) ──────────────────────

def test_csv_roundtrip_preserves_mask():
    """Salvar e reabrir um CSV deve retornar exatamente os mesmos dados."""
    mask = np.zeros((50, 50), dtype=int)
    mask[10:20, 10:20] = 1
    mask[30:40, 30:40] = 2
    informacoes = {
        "colors":     [np.array([255, 255, 0]), np.array([255, 0, 0])],
        "identifier": [1, 2],
        "tissue":     [3, 5],
    }
    area = 1000

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        path = f.name
    try:
        save_mask(path, mask, informacoes, area)
        loaded_mask, loaded_info, loaded_area = load_mask(path)

        assert np.array_equal(mask, loaded_mask)
        assert loaded_area == area
        assert loaded_info["tissue"] == informacoes["tissue"]
        assert loaded_info["identifier"] == informacoes["identifier"]
        for orig, loaded in zip(informacoes["colors"], loaded_info["colors"]):
            assert np.array_equal(orig, loaded)
    finally:
        os.unlink(path)


def test_csv_roundtrip_multi_tissue():
    """Garante que múltiplos tecidos são preservados corretamente."""
    mask = np.zeros((30, 30), dtype=int)
    for i in range(1, 5):
        mask[i*5:(i+1)*5, i*5:(i+1)*5] = i
    informacoes = {
        "colors":     [np.array([c, c, 0]) for c in [255, 200, 150, 100]],
        "identifier": [1, 2, 3, 4],
        "tissue":     [1, 3, 5, 4],
    }
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        path = f.name
    try:
        save_mask(path, mask, informacoes, area=500)
        loaded_mask, loaded_info, _ = load_mask(path)
        assert np.array_equal(mask, loaded_mask)
        assert len(loaded_info["colors"]) == 4
    finally:
        os.unlink(path)


# ── Fluxo 1 — pipeline de imagem sintética ───────────────────────────────────

def test_clahe_superpixel_pipeline():
    """
    Pipeline completo com imagem sintética:
    imagem uint8 → CLAHE → superpixels → máscara simulada → CSV → reload
    """
    # imagem sintética com regiões distintas (simula saída do DICOM pós-processado)
    image = np.zeros((100, 100), dtype=np.uint8)
    image[0:50,  0:50]  = 80
    image[0:50,  50:100] = 150
    image[50:100, 0:50]  = 200
    image[50:100, 50:100] = 40

    # CLAHE
    clahe_img = apply_clahe(image)
    assert clahe_img.shape == image.shape
    assert clahe_img.dtype == np.uint8

    # Superpixels
    segments = compute_superpixels(clahe_img, n_segments=20)
    assert segments.shape == image.shape
    assert len(np.unique(segments)) > 1

    # Simula pintura — marca o superpixel do centro como tecido 1
    segmented_mask = np.zeros_like(image, dtype=int)
    center_label   = segments[50, 50]
    if center_label > 0:
        segmented_mask[segments == center_label] = 1

    # Monta informacoes e salva
    informacoes = {
        "colors":     [np.array([255, 255, 0])],
        "identifier": [1],
        "tissue":     [3],
    }
    area = int(np.count_nonzero(image))

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        path = f.name
    try:
        save_mask(path, segmented_mask, informacoes, area)
        loaded_mask, loaded_info, loaded_area = load_mask(path)

        assert np.array_equal(segmented_mask, loaded_mask)
        assert loaded_area == area
        assert loaded_info["tissue"] == [3]
    finally:
        os.unlink(path)


# ── Fluxo 1 com DICOM real (pula se não houver arquivo) ──────────────────────

DICOM_PATH = r"C:\Users\Pedro Otávio\OneDrive\Documentos\UECE\LAMAC\dataset\images\tc1tr0_024.dcm"

@pytest.mark.skipif(not os.path.exists(DICOM_PATH),
                    reason="arquivo test.dcm não encontrado")
def test_dicom_full_pipeline():
    """
    Pipeline completo com DICOM real:
    dcm → array HU → select_RoI → ConvertToUint8 → CLAHE → superpixels
    """
    import pydicom
    from src.services.dicom_service import dicom2array

    dcm   = pydicom.dcmread(DICOM_PATH, force=True)
    array = dicom2array(dcm)
    assert array is not None

    roi        = select_RoI(array)
    uint8_img  = ConvertToUint8(roi)
    clahe_img  = apply_clahe(uint8_img)
    segments   = compute_superpixels(clahe_img, n_segments=500)

    assert segments.shape == uint8_img.shape
    assert len(np.unique(segments)) > 10
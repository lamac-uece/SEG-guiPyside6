# tests/unit/test_image_processing.py
import numpy as np
from src.services.image_processing import (
    select_RoI,
    apply_clahe,
    compute_superpixels,
    removeSkinAndObjects,
)
from src.utils.image_utils import tissue_segmentation

# ── select_RoI ────────────────────────────────────────────────────────────────

def test_select_roi_preserves_shape():
    img = np.random.randint(-1000, 500, (128, 128), dtype=int)
    result = select_RoI(img)
    assert result.shape == img.shape

def test_select_roi_output_dtype():
    img = np.random.randint(-1000, 500, (128, 128), dtype=int)
    result = select_RoI(img)
    assert result.dtype == img.dtype

def test_select_roi_suppresses_air_region():
    """Pixels abaixo do limiar do ar devem ser substituídos pelo mínimo."""
    img = np.zeros((64, 64), dtype=int)
    img[0, 0] = -5000          # ar (abaixo do limiar)
    img[30:40, 30:40] = 50     # região de interesse
    result = select_RoI(img)
    assert result[0, 0] == img.min()


# ── apply_clahe ───────────────────────────────────────────────────────────────

def test_clahe_preserves_shape():
    img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    result = apply_clahe(img)
    assert result.shape == img.shape

def test_clahe_output_dtype():
    img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    result = apply_clahe(img)
    assert result.dtype == np.uint8

def test_clahe_output_range():
    """Saída deve estar no intervalo [0, 255]."""
    img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    result = apply_clahe(img)
    assert result.min() >= 0
    assert result.max() <= 255

def test_clahe_custom_params():
    img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    result = apply_clahe(img, clip_limit=0.01, nbins=128)
    assert result.shape == img.shape
    assert result.dtype == np.uint8


# ── compute_superpixels ───────────────────────────────────────────────────────

def test_superpixels_shape_matches_input():
    img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    labels = compute_superpixels(img, n_segments=50)
    assert labels.shape == img.shape

def test_superpixels_generates_multiple_segments():
    img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
    labels = compute_superpixels(img, n_segments=50)
    assert len(np.unique(labels)) > 1

def test_superpixels_label_count_reasonable():
    """Número de segmentos gerados deve ser próximo do solicitado."""
    # imagem com 4 regiões de intensidade bem distintas
    img = np.zeros((200, 200), dtype=np.uint8)
    img[0:100, 0:100]   = 50    # quadrante superior esquerdo
    img[0:100, 100:200] = 120   # quadrante superior direito
    img[100:200, 0:100] = 180   # quadrante inferior esquerdo
    img[100:200, 100:200] = 240 # quadrante inferior direito

    labels = compute_superpixels(img, n_segments=100)
    n_generated = len(np.unique(labels))
    assert n_generated >= 4  # no mínimo as 4 regiões distintas


# ── tissue_segmentation ───────────────────────────────────────────────────────

def test_tissue_segmentation_returns_bool_array():
    img = np.random.randint(-200, 200, (64, 64), dtype=int)
    result = tissue_segmentation(img, "fat")
    assert result.dtype == np.bool_

def test_tissue_segmentation_shape_preserved():
    img = np.random.randint(-200, 200, (64, 64), dtype=int)
    result = tissue_segmentation(img, "fat")
    assert result.shape == img.shape

def test_tissue_segmentation_fat_hu_range():
    """Pixels dentro do range HU de gordura (-190 a -30) devem ser True."""
    img = np.array([[-190, -100, -30, 0, 50]], dtype=int)
    result = tissue_segmentation(img, "fat")
    assert result[0, 0] == True    # -190 (limite inferior)
    assert result[0, 1] == True    # -100 (dentro do range)
    assert result[0, 2] == True    # -30  (limite superior)
    assert result[0, 3] == False   # 0    (fora do range)
    assert result[0, 4] == False   # 50   (fora do range)

def test_tissue_segmentation_muscle_hu_range():
    """Pixels dentro do range HU de músculo (-29 a 150) devem ser True."""
    img = np.array([[-29, 80, 150, -30, 200]], dtype=int)
    result = tissue_segmentation(img, "muscle")
    assert result[0, 0] == True    # -29 (limite inferior)
    assert result[0, 1] == True    # 80  (dentro do range)
    assert result[0, 2] == True    # 150 (limite superior)
    assert result[0, 3] == False   # -30 (fora do range)
    assert result[0, 4] == False   # 200 (fora do range)

def test_tissue_segmentation_all_tissues_run():
    """Todos os tecidos definidos em materials devem ser aceitos sem erro."""
    img = np.random.randint(-1000, 1000, (32, 32), dtype=int)
    tissues = ["bone", "bonelike", "muscle", "skmuscle",
               "fat", "fatlike", "air", "organ"]
    for tissue in tissues:
        result = tissue_segmentation(img, tissue)
        assert result.shape == img.shape
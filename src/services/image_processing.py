import cv2
import numpy as np
from skimage.morphology import disk
from skimage.measure import label, regionprops
from skimage.segmentation import slic
from skimage.util import img_as_float
import scipy.ndimage as ndi

from src.models.tissue_config import materials
from src.utils.image_utils import (
    remove_small_CCs,
    bitwise_minus,
    compose_muscle_mask,
    tissue_segmentation
)

def select_RoI(dicom_image_array):
    """
    Seleciona a região de interesse da imagem DICOM,
    removendo o fundo e isolando o corpo.
    """
    mask = np.ones_like(dicom_image_array)
    mask[dicom_image_array < materials['air'][0][1]] = 0
    labels = label(mask, background=0, return_num=False, connectivity=1)
    mask = np.array(labels == np.argmax(np.bincount(labels.flat)[1:]) + 1, dtype=int)
    output = np.copy(dicom_image_array)
    output[mask==0] = np.min(dicom_image_array)
    return output

def apply_clahe(image: np.ndarray,
                clip_limit: float = 0.03,
                nbins: int = 256) -> np.ndarray:
    """
    Aplica equalização adaptativa de histograma (CLAHE) na imagem.
    Utiliza skimage.exposure.equalize_adapthist, normalizando
    a entrada para [0,1] e devolvendo uint8 em [0,255].
    """
    from skimage import exposure

    normalized = image / 255.0
    equalized = exposure.equalize_adapthist(
        normalized,
        clip_limit=clip_limit,
        nbins=nbins
    )
    if equalized.max() <= 1:
        equalized = (equalized * 255).astype(np.uint8)
    return equalized


def compute_superpixels(image: np.ndarray,
                        n_segments: int = 2000,
                        sigma: int = 1,
                        compactness: float = 0.05,
                        start_label: int = 1,
                        max_num_iter: int = 10,
                        min_size_factor: float = 0.5,
                        max_size_factor: float = 3.0,
                        background_threshold: int = 20) -> np.ndarray:
    """
    Gera segmentação SLIC sobre a imagem e retorna o mapa de labels.
    Pixels abaixo de background_threshold são zerados (fundo/ar).
    """
    segments = slic(
        image,
        n_segments=n_segments,
        sigma=sigma,
        compactness=compactness,
        channel_axis=None,
        start_label=start_label,
        max_num_iter=max_num_iter,
        min_size_factor=min_size_factor,
        max_size_factor=max_size_factor
    )
    segments[image < background_threshold] = 0
    return segments

def removeSkinAndObjects(dicom_image_array, m):
    """
    Remove objetos externos à mesa e a camada de pele,
    retornando apenas a região interna do corpo.
    """
    dicom_image_array = select_RoI(dicom_image_array)

    rows, cols = dicom_image_array.shape
    bone_mask       = tissue_segmentation(dicom_image_array, 'bone')
    bonelike_mask   = tissue_segmentation(dicom_image_array, 'bonelike')
    muscle_mask     = tissue_segmentation(dicom_image_array, 'muscle')
    skmuscle_mask   = tissue_segmentation(dicom_image_array, 'skmuscle')
    fat_mask        = tissue_segmentation(dicom_image_array, 'fat')
    fatlike_mask    = tissue_segmentation(dicom_image_array, 'fatlike')
    air_mask        = tissue_segmentation(dicom_image_array, 'air')

    original_muscle_mask = np.copy(muscle_mask)
    muscle_mask = compose_muscle_mask(muscle_mask, skmuscle_mask, tol=10)

    body_with_skin_mask = np.ones_like(muscle_mask, dtype=bool)
    body_with_skin_mask[air_mask!=0] = 0
    body_with_skin_mask = ndi.binary_fill_holes(body_with_skin_mask)
    body_edt = ndi.distance_transform_edt(body_with_skin_mask)
    body_perimeter = np.sum([body_edt==1])
    
    row_c, col_c = ndi.center_of_mass(body_with_skin_mask)
    row_c = int( np.round(row_c) )
    col_c = int( np.round(col_c) )

    cumulative_sum = 0
    thick = 1
    while cumulative_sum < m * body_perimeter:
        cumulative_sum += np.sum(fat_mask[body_edt==thick])
        thick += 1
    
    off_skin = np.ones_like(muscle_mask, dtype=bool)
    off_skin[body_edt <= thick] = 0

    muscle_mask = np.bitwise_and(muscle_mask, off_skin)

    thres = int( np.round( 0.0030 * np.sum(body_with_skin_mask) ) )
    print('Small objects threshold:', thres)

    aux_muscle_mask = remove_small_CCs(muscle_mask, thres=thres)

    body_mask = np.bitwise_or(fat_mask, aux_muscle_mask)
    body_mask = ndi.binary_opening(
        ndi.binary_fill_holes(body_mask),
        iterations=3, 
        structure=disk(1) 
    ) 
    body_mask = remove_small_CCs(body_mask, thres=thres)

    skin_mask = bitwise_minus(body_with_skin_mask, body_mask)
    skin_mask[body_edt==1] = 1
    skin_mask = np.bitwise_and(skin_mask, 1 - off_skin)
    skin_mask = ndi.binary_closing(skin_mask, iterations=3, structure=disk(1))
    
    # fig_size = (16,16)
    # fig = plt.figure(figsize=fig_size)
    # ax1 = fig.add_subplot(221)
    
    minimo = np.min(dicom_image_array) 
    dicom_image_array[skin_mask==1] = minimo
    return dicom_image_array
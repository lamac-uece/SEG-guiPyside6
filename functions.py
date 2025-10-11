from skimage import data, img_as_float
from skimage import exposure
from skimage import color
import pydicom
import pydicom as dicom
from pydicom import dcmread
from pydicom.data import get_testdata_files
import numpy as np
from skimage.io import *
import cv2 as cv
from PIL import ImageFile
#ImageFile.LOAD_TRUNCATED_IMAGES = True
from skimage.segmentation import slic
from skimage.segmentation import mark_boundaries
from skimage.measure import label
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
import matplotlib.backends.backend_qt5 as backend
from PySide6.QtWidgets import *
from PySide6.QtGui import *
# import pylibjpeg
# import libjpeg
import numpy as np
import matplotlib.pyplot as plt
import scipy.ndimage as ndi
import pydicom
from skimage import exposure
from skimage.measure import label, regionprops
from skimage.morphology import disk
from enum import Enum
def bitwise_minus(img1, img2):
    """Set subtraction applied to the images."""
    return np.bitwise_and( img1, 1 - img2 )
class _Mode(str, Enum):
    NONE = ""
    CLEAR = "clear"

    def __str__(self):
        return self.value

    @property
    def _navigate_mode(self):
        return self.name if self is not _Mode.NONE else None
def remove_small_CCs(mask, thres=100, connectivity=1):
    labels, num_labels = label(mask, background=0, \
                               return_num=True, connectivity=connectivity)
    output = np.zeros_like(labels)
    for lst in np.where( np.bincount(labels.flat)[1:] > thres ):
        for k in lst:
            output[ labels==(k+1) ] = 1
    return output
def find_extreme_points(img, thresh=None):
    """Find the left, right, top, and bottom 
    extreme points of a binary image.
    Optional threshold to convert gray image 
    to binary image.
    """

    binary_img = np.copy(img)
    if thresh is not None:
        float(thresh)
        binary_img[ img <  thresh ] = 0
        binary_img[ img >= thresh ] = 1
    
    min_row, min_col, max_row, max_col = regionprops(binary_img.astype(int))[0].bbox
    
    # format is [row, col], NOT [x, y]
    leftmost   = np.array( [np.argmax(binary_img[:,min_col]),   min_col] )
    rightmost  = np.array( [np.argmax(binary_img[:,max_col-1]), max_col-1] )
    topmost    = np.array( [min_row,   np.argmax(binary_img[min_row,:])] )
    bottommost = np.array( [max_row-1, np.argmax(binary_img[max_row-1,:])] )

    return leftmost, rightmost, topmost, bottommost
def compose_muscle_mask(muscle, skmuscle, tol=10):
    min_row, min_col, max_row, max_col = regionprops(skmuscle.astype(int))[0].bbox
    find_extreme_points(skmuscle, thresh=None)
    min_col = int(min_col)
    max_col = int(max_col)
    min_row = int(min_row)
    output = np.copy(skmuscle)
    output[min_row-tol:min_row+tol,min_col:max_col] = muscle[min_row-tol:min_row+tol,min_col:max_col]
    return output
def tissue_segmentation(dicom_image_array, tissue):
    """Tissue segmentation

    Returns a mask of the image where the tissue was found. The tissue is a strip
    of Hounsfield Units value in the "material"'s dict
    """
    segm_img = np.zeros_like(dicom_image_array, dtype=np.bool_)
    segm_img[ (dicom_image_array >= materials[tissue][0][0]) &
             (dicom_image_array <= materials[tissue][0][1]) ] = 1
    return segm_img
def select_RoI(dicom_image_array):
    """Select Region of Interest

    Removes unwanted objects from the image, 
    such as the tomograph "bed" and sheets.
    """
    mask = np.ones_like(dicom_image_array)
    mask[dicom_image_array < materials['air'][0][1]] = 0
    labels = label(mask, background=0, return_num=False, connectivity=1)
    mask = np.array(labels == np.argmax(np.bincount(labels.flat)[1:]) + 1, dtype=int)
    output = np.copy(dicom_image_array)
    output[mask==0] = np.min(dicom_image_array)
    return output
# Colors
colors = {
    'black':  [(0,0,0),       0],
    'white':  [(255,255,255), 1],
    'red':    [(255,0,0),     2],
    'green':  [(0,255,0),     3],
    'blue':   [(0,0,255),     4],
    'yellow': [(255,255,0),   5],
    'orange': [(255,140,0),   6],
    'gray':   [(127,127,127), 9]
}
# HU range for each material
# 'material': [(minimum value, maximum value), 'color']
# Although 'muscle' minimum value should be 31 (and not -29).
# this helps in the segmentation process
materials = {
    'bone':         [(   500, 10000), 'white' ],
    'bonelike':     [(   160, 10000), 'white' ],
    'muscle':       [(   -29,   150), 'orange'], #'muscle': [(31, 150), 'blue'],
    'skmuscle':     [(    10,    40), 'red'   ],
    'organ':        [(   -29,    30), 'green' ],
    'musclelike':   [(   -50,   150), 'orange'], # includes part of subcutaneous fat
    'fat':          [(  -190,   -30), 'yellow'], 
    'scfat':        [(  -190,   -30), 'blue'  ], # subcutaneous fat
    'imfat':        [(  -150,   -50), 'green' ], # visceral fat (ver e-mail da Sara)
    'fatlike':      [(  -190,   -10), 'yellow'], # fat with a bit of muscle
    'air':          [(-10000,  -300), 'black' ]

}
def dicom2array(dcm):
    # Detecta o tipo de codificação da imagem DICOM
    tsuid = dcm.file_meta.TransferSyntaxUID

    if tsuid == "1.2.840.10008.1.2.4.70":
        print("Compressed DICOM detected (JPEG Lossless). Attempting to decompress...")
        try:
            dcm.decompress(handler_name="pylibjpeg")
            print("Decompression successful.")
        except Exception as e:
            print(f"Failed to decompress image: {e}")
            return None
    else:
        print("Standard uncompressed DICOM detected. Proceeding with normal reading.")

    # Tenta converter a imagem para array
    try:
        img_raw = np.float64(dcm.pixel_array)
        output = np.array(dcm.RescaleSlope * img_raw + dcm.RescaleIntercept, dtype=int)
        print("DICOM image successfully converted to array.")
        return output
    except Exception as e:
        print(f"Failed to convert DICOM to array: {e}")
        return None
def ConvertToUint8(dicom_image_array):
    orig_min = dicom_image_array.min()
    orig_max = dicom_image_array.max()
    target_min = 0.0
    target_max = 255.0
    dicom_image_array = (dicom_image_array-orig_min)*((target_max- 
    target_min)/(orig_max-orig_min))+target_min
    dicom_image_array = dicom_image_array.astype(np.uint8)
    return dicom_image_array
class CustomDialog(QDialog):
    def __init__(self):
        super().__init__()

        QBtn = QDialogButtonBox.Yes | QDialogButtonBox.No
        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.setWindowTitle("LAMAC")
        self.setWindowIcon(QPixmap("./icon.png"))
        self.layout = QVBoxLayout()
        message = QLabel("<center>Deseja aproveitar a mascara</center> \n<center>do arquivo .csv atual?</center>")
        self.layout.addWidget(message)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)
    def show(self):
        return self.exec_()
def removeSkinAndObjects(dicom_image_array, m):
    dicom_image_array = select_RoI(dicom_image_array)
    rows, cols = dicom_image_array.shape
    # Segmentation using HU standard values without skin
    bone_mask       = tissue_segmentation(dicom_image_array, 'bone')
    bonelike_mask   = tissue_segmentation(dicom_image_array, 'bonelike')
    muscle_mask     = tissue_segmentation(dicom_image_array, 'muscle')
    # musclelike_mask = tissue_segmentation(dicom_image_array, 'musclelike')
    skmuscle_mask   = tissue_segmentation(dicom_image_array, 'skmuscle')
    fat_mask        = tissue_segmentation(dicom_image_array, 'fat')
    fatlike_mask    = tissue_segmentation(dicom_image_array, 'fatlike')
    air_mask        = tissue_segmentation(dicom_image_array, 'air')

    # Use skeletal muscle mask, except for a narrow strip on the top
    original_muscle_mask = np.copy(muscle_mask)
    muscle_mask = compose_muscle_mask(muscle_mask, skmuscle_mask, tol=10)

    # Calculate body_mask, its EDT, and its perimeter
    body_with_skin_mask = np.ones_like(muscle_mask, dtype=bool)
    body_with_skin_mask[air_mask!=0] = 0
    body_with_skin_mask = ndi.binary_fill_holes(body_with_skin_mask)
    body_edt = ndi.distance_transform_edt(body_with_skin_mask)
    body_perimeter = np.sum([body_edt==1])
    # Calculate body with skin centroid
    row_c, col_c = ndi.center_of_mass(body_with_skin_mask)
    row_c = int( np.round(row_c) )
    col_c = int( np.round(col_c) )

    # Use body_with_skin_mask information above to
    # remove skin from muscle_mask and from fat_mask
    cumulative_sum = 0
    thick = 1
    while cumulative_sum < m*body_perimeter:
        cumulative_sum += np.sum(fat_mask[body_edt==thick])
        thick += 1
    # off_skin is the region inside the skin
    off_skin = np.ones_like(muscle_mask, dtype=bool)
    off_skin[body_edt <= thick] = 0

    # First estimate for muscle_mask (skin removed)
    muscle_mask = np.bitwise_and(muscle_mask, off_skin)

    # Threshold used to remove small objects from body_mask,
    # based on the average of few examples: factor = 0.0025 or 0.0030
    thres = int( np.round( 0.0030 * np.sum(body_with_skin_mask) ) )
    print('Small objects threshold:', thres)

    # Remove temporarily small objects from muscle mask
    aux_muscle_mask = remove_small_CCs(muscle_mask, thres=thres)

    # Calculate body mask
    body_mask = np.bitwise_or(fat_mask, aux_muscle_mask)
    body_mask = ndi.binary_opening( ndi.binary_fill_holes(body_mask), \
                                iterations=3, structure=disk(1) ) 
    body_mask = remove_small_CCs(body_mask, thres=thres)

    # Calculate skin_mask, adding 1-pixel thick external line
    skin_mask = bitwise_minus(body_with_skin_mask, body_mask)
    skin_mask[body_edt==1] = 1
    skin_mask = np.bitwise_and(skin_mask, 1 - off_skin)
    skin_mask = ndi.binary_closing(skin_mask, iterations=3, structure=disk(1))
    fig_size = (16,16)
    fig = plt.figure(figsize=fig_size)
    ax1 = fig.add_subplot(221)
    minimo = np.min(dicom_image_array) 
    dicom_image_array[skin_mask==1] = minimo
    return dicom_image_array
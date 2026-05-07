import numpy as np
from skimage.measure import label, regionprops

def bitwise_minus(img1, img2):
    """Set subtraction applied to the images."""
    return np.bitwise_and( img1, 1 - img2 )

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

def remove_small_CCs(mask, thres=100, connectivity=1):
    labels, num_labels = label(mask, background=0, \
                               return_num=True, connectivity=connectivity)
    output = np.zeros_like(labels)
    for lst in np.where( np.bincount(labels.flat)[1:] > thres ):
        for k in lst:
            output[ labels==(k+1) ] = 1
    return output

def compose_muscle_mask(muscle, skmuscle, tol=10):
    min_row, min_col, max_row, max_col = regionprops(skmuscle.astype(int))[0].bbox
    find_extreme_points(skmuscle, thresh=None)
    min_col = int(min_col)
    max_col = int(max_col)
    min_row = int(min_row)
    output = np.copy(skmuscle)
    output[min_row-tol:min_row+tol,min_col:max_col] = muscle[min_row-tol:min_row+tol,min_col:max_col]
    return output

def ConvertToUint8(dicom_image_array):
    orig_min = dicom_image_array.min()
    orig_max = dicom_image_array.max()
    if orig_max == orig_min:
        return np.zeros_like(dicom_image_array, dtype=np.uint8)
    target_min = 0.0
    target_max = 255.0
    dicom_image_array = (dicom_image_array-orig_min)*((target_max- 
    target_min)/(orig_max-orig_min))+target_min
    dicom_image_array = dicom_image_array.astype(np.uint8)
    return dicom_image_array
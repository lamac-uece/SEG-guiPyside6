from src.utils.image_utils import bitwise_minus, remove_small_CCs, ConvertToUint8
import numpy as np

def test_bitwise_minus_removes_overlap():
    a = np.array([[1, 1], [0, 1]])
    b = np.array([[1, 0], [0, 0]])
    result = bitwise_minus(a, b)
    assert result[0, 0] == 0
    assert result[0, 1] == 1

def test_convert_to_uint8_all_zeros():
    img = np.zeros((3, 3), dtype=float)
    result = ConvertToUint8(img)
    assert result.dtype == np.uint8
    assert np.all(result == 0)

def test_remove_small_ccs_removes_noise():
    mask = np.zeros((200, 200), dtype=np.uint8)
    mask[1, 1] = 1
    mask[20:120, 20:120] = 1
    result = remove_small_CCs(mask)
    assert result[1, 1] == 0
    assert result[70, 70] == 1
import os
import numpy as np

def get_dicom_identifier(dicom, file_path: str) -> str:
    """
    Retorna um identificador único da imagem DICOM, usado para verificar
    se uma máscara .csv salva anteriormente corresponde ao arquivo aberto.

    Usa o SOPInstanceUID quando disponível; caso contrário, recorre ao
    caminho absoluto do arquivo.
    """
    sop_uid = getattr(dicom, "SOPInstanceUID", None)
    if sop_uid:
        return str(sop_uid)
    return os.path.abspath(file_path)

def _decompress_if_needed(dicom) -> bool:
    """
    Descomprime o DICOM se necessário.
    Retorna True se pronto para leitura, False se falhou.
    """
    tsuid = dicom.file_meta.TransferSyntaxUID
    if tsuid == "1.2.840.10008.1.2.4.70":
        print("Compressed DICOM detected (JPEG Lossless). Attempting to decompress...")
        try:
            dicom.decompress(handler_name="pylibjpeg")
            print("Decompression successful.")
        except Exception as e:
            print(f"Failed to decompress image: {e}")
            return False
    return True

def dicom2array(dicom) -> np.ndarray | None:
    """
    Converte um objeto pydicom para numpy array com escala HU.
    Retorna None em caso de falha.
    """
    if not _decompress_if_needed(dicom):
        return None
    try:
        img_raw = np.float64(dicom.pixel_array)
        output = np.array(
            dicom.RescaleSlope * img_raw + dicom.RescaleIntercept,
            dtype=int
        )
        print("DICOM image successfully converted to array.")
        return output
    except Exception as e:
        print(f"Failed to convert DICOM to array: {e}")
        return None
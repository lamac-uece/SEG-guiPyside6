# src/services/mask_io.py
import numpy as np


def load_mask(path: str) -> tuple:
    """
    Lê um arquivo .csv de máscara segmentada.

    Formato esperado:
        - Linhas 0..N-3 : linhas da segmentedMask (inteiros separados por vírgula)
        - Linha N-2     : informacoes — cada tecido como "r,g,b,identifier,tissue "
        - Linha N-1     : area (inteiro)

    Retorna:
        segmented_mask : np.ndarray dtype=int
        informacoes    : dict com chaves 'colors', 'identifier', 'tissue'
        area           : int
    """
    with open(path, 'r') as f:
        lines = f.readlines()

    area = int(lines[-1].strip())

    informacoes_str = lines[-2].split(" ")[:-1]
    for i in range(len(informacoes_str)):
        informacoes_str[i] = informacoes_str[i].split(",")
    informacoes_int = np.array(informacoes_str, dtype=int)

    informacoes = {"colors": [], "identifier": [], "tissue": []}
    for row in informacoes_int:
        informacoes["colors"].append(np.array([row[0], row[1], row[2]]))
        informacoes["identifier"].append(row[3])
        informacoes["tissue"].append(row[4])

    temp_mask = []
    for i in range(len(lines) - 2):
        temp_mask.append(np.array(lines[i].split(","), dtype=int))
    segmented_mask = np.array(temp_mask, dtype=int)

    return segmented_mask, informacoes, area


def save_mask(path: str,
              segmented_mask: np.ndarray,
              informacoes: dict,
              area: int) -> None:
    """
    Salva a máscara segmentada em arquivo .csv.

    Formato gerado:
        - Linhas 0..N-3 : linhas da segmented_mask
        - Linha N-2     : informacoes — cada tecido como "r,g,b,identifier,tissue "
        - Linha N-1     : area
    """
    # salva a máscara linha a linha
    np.savetxt(path, segmented_mask, fmt='%d', delimiter=',')

    # abre em modo append para adicionar informacoes e area
    with open(path, 'ab') as f:
        informacoes_lista = []
        for i in range(len(informacoes["colors"])):
            informacoes_lista.append([
                informacoes["colors"][i][0],
                informacoes["colors"][i][1],
                informacoes["colors"][i][2],
                informacoes["identifier"][i],
                informacoes["tissue"][i],
            ])
        np.savetxt(f, np.array(informacoes_lista), fmt='%d',
                   newline=' ', delimiter=',')
        f.write(b"\n")
        np.savetxt(f, [area], fmt='%d', delimiter=',')
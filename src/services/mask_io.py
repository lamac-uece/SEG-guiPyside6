import numpy as np


def load_mask(path: str) -> tuple:
    """
    Lê um arquivo .csv de máscara segmentada.

    Formato esperado:
        - Linhas 0..N-3 : linhas da segmentedMask (inteiros separados por vírgula)
        - Linha N-2     : informacoes — cada tecido como "r,g,b,identifier,tissue "
        - Linha N-1     : area (inteiro)
        - Linha N       : source_id (opcional) — identificador do DICOM de origem

    A linha de area é sempre um inteiro puro; se a última linha do arquivo
    não for um inteiro, ela é o source_id e a linha de area passa a ser a
    penúltima (arquivos antigos não têm essa linha extra).

    Retorna:
        segmented_mask : np.ndarray dtype=int
        informacoes    : dict com chaves 'colors', 'identifier', 'tissue'
        area           : int
        source_id      : str (vazio se o arquivo não tiver essa informação)
    """
    with open(path, 'r') as f:
        lines = f.readlines()

    try:
        area = int(lines[-1].strip())
        source_id = ""
        informacoes_line = lines[-2]
        mask_lines = lines[:-2]
    except ValueError:
        source_id = lines[-1].strip()
        area = int(lines[-2].strip())
        informacoes_line = lines[-3]
        mask_lines = lines[:-3]

    informacoes_str = informacoes_line.split(" ")[:-1]
    for i in range(len(informacoes_str)):
        informacoes_str[i] = informacoes_str[i].split(",")
    informacoes_int = np.array(informacoes_str, dtype=int)

    informacoes = {"colors": [], "identifier": [], "tissue": []}
    for row in informacoes_int:
        informacoes["colors"].append(np.array([row[0], row[1], row[2]]))
        informacoes["identifier"].append(row[3])
        informacoes["tissue"].append(row[4])

    temp_mask = []
    for line in mask_lines:
        temp_mask.append(np.array(line.split(","), dtype=int))
    segmented_mask = np.array(temp_mask, dtype=int)

    return segmented_mask, informacoes, area, source_id


def save_mask(path: str,
              segmented_mask: np.ndarray,
              informacoes: dict,
              area: int,
              source_id: str = "") -> None:
    """
    Salva a máscara segmentada em arquivo .csv.

    Formato gerado:
        - Linhas 0..N-3 : linhas da segmented_mask
        - Linha N-2     : informacoes — cada tecido como "r,g,b,identifier,tissue "
        - Linha N-1     : area
        - Linha N       : source_id (apenas se informado)
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
        if source_id:
            f.write(source_id.encode() + b"\n")
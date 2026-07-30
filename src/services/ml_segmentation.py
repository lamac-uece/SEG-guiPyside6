"""
Serviço de segmentação automática.

Todos os modelos registrados em `ml_tissue_config.ML_TISSUE_MODELS` são
carregados uma vez, no início da aplicação (`load_all_models()`, chamado
por `app.py`). A partir daí, `predict_mask()` só executa a inferência —
nunca carrega nada em tempo de clique.

Carregamento é isolado por tecido: se o `.keras` de um tecido estiver
ausente ou corrompido, isso não impede os demais tecidos de carregar. A
lista de falhas fica disponível via `load_all_models()` para o chamador
decidir como avisar o usuário.

Sem dependência de UI — mesmo padrão dos demais services do projeto.
"""

import os

import cv2
import numpy as np

from src.models.ml_tissue_config import ML_TISSUE_MODELS, MLModelSpec

# modelos carregados com sucesso, por tecido — populado só por load_all_models().
_LOADED_MODELS: dict = {}


class MLSegmentationError(Exception):
    """Erro ao carregar um modelo ou executar a inferência."""


def load_all_models() -> list[tuple[str, str]]:
    """
    Carrega, uma única vez, todos os modelos registrados em
    ML_TISSUE_MODELS. Deve ser chamado no startup da aplicação.

    Falha em um tecido não impede o carregamento dos demais: cada um roda
    em seu próprio try/except.

    Return:
        Lista de (tecido, motivo_da_falha) para os tecidos que NÃO
        carregaram. Lista vazia significa que todos carregaram com sucesso.
        Tecidos que carregarem ficam disponíveis em available_tissues().
    """
    import keras

    failures = []
    for tissue_key, spec in ML_TISSUE_MODELS.items():
        try:
            if not os.path.exists(spec.model_path):
                raise MLSegmentationError(
                    f"Arquivo não encontrado: '{spec.model_path}'."
                )
            _LOADED_MODELS[tissue_key] = keras.models.load_model(spec.model_path)
        except Exception as e:
            failures.append((tissue_key, str(e)))
    return failures


def available_tissues() -> list[str]:
    """
    Tecidos com modelo efetivamente carregado — só estes devem ser
    oferecidos ao usuário na hora de escolher o tecido a segmentar.
    """
    return list(_LOADED_MODELS.keys())


def is_tissue_loaded(tissue_key: str) -> bool:
    return tissue_key in _LOADED_MODELS


def preprocess(image: np.ndarray, target_size: int) -> np.ndarray:
    """
    Redimensiona e normaliza a imagem para o formato de entrada da rede:
    (1, target_size, target_size, 1), valores em [0, 1].
    """
    resized = cv2.resize(image, (target_size, target_size), interpolation=cv2.INTER_LINEAR)
    normalized = resized.astype(np.float32) / 255.0
    return normalized[np.newaxis, :, :, np.newaxis]


def predict_mask(image: np.ndarray, tissue_key: str) -> np.ndarray:
    """
    Executa a segmentação automática para o tecido informado.

    Args:
        image: `dicom_image_array` (uint8, 2D), como está em tela.
        tissue_key: chave em `dictTissues` (ex.: "Fat").

    Return:
        Máscara booleana 2D no tamanho ORIGINAL de `image`, True nos
        pixels classificados como o tecido escolhido.

    Levanta MLSegmentationError se o tecido não tiver modelo carregado —
    o chamador (controller) deve garantir isso de antemão via
    is_tissue_loaded()/available_tissues(), então isso só deve disparar
    em uso indevido da API.
    """
    model = _LOADED_MODELS.get(tissue_key)
    if model is None:
        raise MLSegmentationError(
            f"Modelo de '{tissue_key}' não está carregado. "
            "Tecidos disponíveis: " + ", ".join(available_tissues() or ["nenhum"])
        )
    spec: MLModelSpec = ML_TISSUE_MODELS[tissue_key]

    original_shape = image.shape
    net_input = preprocess(image, spec.input_size)

    prediction = model.predict(net_input, verbose=0)[0, :, :, 0]
    binary_mask = prediction > spec.threshold

    mask_uint8 = binary_mask.astype(np.uint8)
    resized_back = cv2.resize(
        mask_uint8, (original_shape[1], original_shape[0]),
        interpolation=cv2.INTER_NEAREST,
    )
    return resized_back.astype(bool)
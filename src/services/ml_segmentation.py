"""
Serviço de segmentação automática.

Todos os modelos registrados em `ml_tissue_config.ML_TISSUE_MODELS` são
carregados uma vez, no início da aplicação (`load_all_models()`, chamado
por `app.py`), como sessões `onnxruntime.InferenceSession`. A partir daí,
`predict_mask()`/`predict_masks()` só executam a inferência — nunca
carregam nada em tempo de clique.

Carregamento é isolado por modelo: se o `.onnx` de um modelo estiver
ausente ou corrompido, isso não impede os demais de carregar. A lista de
falhas fica disponível via `load_all_models()` para o chamador decidir
como avisar o usuário.

Sem dependência de UI (nem de Qt) — mesmo padrão dos demais services do
projeto, e importante aqui especificamente porque `predict_mask`/
`predict_masks` rodam dentro de um worker de thread (ver
`src/workers/inference_worker.py`): nada aqui pode tocar em widgets.
"""

import os

import cv2
import numpy as np
import onnxruntime as ort

from src.models.ml_tissue_config import ML_TISSUE_MODELS, MODE_MODEL, MLModelSpec

# sessões ONNX carregadas com sucesso, por chave de modelo (ver
# ML_TISSUE_MODELS) — populado só por load_all_models().
_LOADED_SESSIONS: dict[str, ort.InferenceSession] = {}


class MLSegmentationError(Exception):
    """Erro ao carregar um modelo ou executar a inferência."""


def load_all_models() -> list[tuple[str, str]]:
    """
    Carrega, uma única vez, todos os modelos registrados em
    ML_TISSUE_MODELS. Deve ser chamado no startup da aplicação.

    Falha em um modelo não impede o carregamento dos demais: cada um roda
    em seu próprio try/except.

    Return:
        Lista de (chave_do_modelo, motivo_da_falha) para os modelos que
        NÃO carregaram. Lista vazia significa que todos carregaram com
        sucesso.
    """
    failures = []
    for model_key, spec in ML_TISSUE_MODELS.items():
        try:
            if not os.path.exists(spec.model_path):
                raise MLSegmentationError(
                    f"Arquivo não encontrado: '{spec.model_path}'."
                )
            _LOADED_SESSIONS[model_key] = ort.InferenceSession(
                spec.model_path, providers=["CPUExecutionProvider"]
            )
        except Exception as e:
            failures.append((model_key, str(e)))
    return failures


def is_model_loaded(model_key: str) -> bool:
    return model_key in _LOADED_SESSIONS


def available_tissues(mode: str = "semi_auto") -> list[str]:
    """
    Tecidos disponíveis para o modo pedido ("semi_auto" ou "auto") — só se
    o modelo que alimenta esse modo (ver MODE_MODEL) tiver carregado.
    """
    model_key = MODE_MODEL[mode]
    if model_key not in _LOADED_SESSIONS:
        return []
    return list(ML_TISSUE_MODELS[model_key].tissues)


def is_tissue_loaded(tissue_key: str, mode: str = "semi_auto") -> bool:
    return tissue_key in available_tissues(mode)


def preprocess(image: np.ndarray, target_size: int) -> np.ndarray:
    """
    Redimensiona e normaliza a imagem para o formato de entrada da rede:
    (1, target_size, target_size, 1), valores em [0, 1].
    """
    resized = cv2.resize(image, (target_size, target_size), interpolation=cv2.INTER_LINEAR)
    normalized = resized.astype(np.float32) / 255.0
    return normalized[np.newaxis, :, :, np.newaxis]


def _run_session(model_key: str, net_input: np.ndarray) -> np.ndarray:
    """
    Roda a sessão ONNX de `model_key` e devolve as predições no formato
    (H, W, num_tissues), valores em [0, 1] (saída sigmoid, sem threshold).

    A rede foi exportada com saída (1, H, W, num_tissues, 1) — squeeze do
    batch (eixo 0) e do eixo extra (eixo -1, herdado do Reshape usado no
    treino para compatibilizar com a loss multiclasse).
    """
    session = _LOADED_SESSIONS.get(model_key)
    if session is None:
        raise MLSegmentationError(
            f"Modelo '{model_key}' não está carregado. "
            "Modelos disponíveis: " + ", ".join(_LOADED_SESSIONS or ["nenhum"])
        )
    input_name = session.get_inputs()[0].name
    output = session.run(None, {input_name: net_input})[0]
    return np.squeeze(output, axis=(0, -1))


def _resolve_conflicts(
    binary_channels: np.ndarray,
    tissues: tuple[str, ...],
    conflict_priority: tuple[str, ...],
) -> np.ndarray:
    """
    Os canais de um modelo multiclasse são sigmoids independentes
    (multi-label) — um pixel pode "ativar" mais de um tecido ao mesmo
    tempo. Nesse caso, aplica `conflict_priority`: o tecido de maior
    prioridade (primeiro na tupla) vence a disputa; os demais perdem
    aquele pixel especificamente (continuam valendo em todo o resto onde
    não há sobreposição). Tecido fora de `conflict_priority` nunca vence
    uma disputa.

    Função pura — não modifica `binary_channels`; se `conflict_priority`
    estiver vazia, devolve os canais inalterados (sem regra de conflito).
    """
    if not conflict_priority:
        return binary_channels

    overlap = binary_channels.sum(axis=-1) > 1
    if not overlap.any():
        return binary_channels.copy()

    priority_index = {tissue: i for i, tissue in enumerate(conflict_priority)}
    ranks = np.array([
        priority_index.get(tissue, len(conflict_priority)) for tissue in tissues
    ])
    # por pixel, o melhor (menor) rank entre os canais ativos ali
    best_rank = np.where(binary_channels, ranks, len(conflict_priority) + 1).min(axis=-1)

    resolved = binary_channels.copy()
    for i in range(len(tissues)):
        loses = overlap & binary_channels[:, :, i] & (ranks[i] != best_rank)
        resolved[:, :, i] = resolved[:, :, i] & ~loses
    return resolved


def predict_masks(model_key: str, image: np.ndarray) -> dict[str, np.ndarray]:
    """
    Roda a inferência multiclasse completa de `model_key` e devolve uma
    máscara booleana 2D (tamanho ORIGINAL de `image`) por tecido coberto
    por esse modelo, já com sobreposição de canais resolvida (ver
    `_resolve_conflicts`).

    Args:
        model_key: chave em ML_TISSUE_MODELS (ex.: "R2-Multiclasse").
        image: `dicom_image_array` (uint8, 2D), como está em tela.
    """
    spec: MLModelSpec = ML_TISSUE_MODELS[model_key]
    original_shape = image.shape
    net_input = preprocess(image, spec.input_size)

    channels = _run_session(model_key, net_input)
    binary_channels = channels > spec.threshold
    resolved = _resolve_conflicts(binary_channels, spec.tissues, spec.conflict_priority)

    masks = {}
    for i, tissue in enumerate(spec.tissues):
        mask_uint8 = resolved[:, :, i].astype(np.uint8)
        resized_back = cv2.resize(
            mask_uint8, (original_shape[1], original_shape[0]),
            interpolation=cv2.INTER_NEAREST,
        )
        masks[tissue] = resized_back.astype(bool)
    return masks


def predict_mask(image: np.ndarray, tissue_key: str) -> np.ndarray:
    """
    Executa a segmentação automática para um único tecido — modo
    Semi-Auto. Roda a inferência completa do modelo que alimenta esse modo
    (MODE_MODEL["semi_auto"]) e extrai só o canal de `tissue_key`. Não há
    mais modelo binário dedicado por tecido — este é hoje o único caminho.

    Return:
        Máscara booleana 2D no tamanho ORIGINAL de `image`, True nos
        pixels classificados como o tecido escolhido.

    Levanta MLSegmentationError se o modelo do modo Semi-Auto não estiver
    carregado, ou se `tissue_key` não for coberto por ele.
    """
    model_key = MODE_MODEL["semi_auto"]
    spec = ML_TISSUE_MODELS[model_key]
    if tissue_key not in spec.tissues:
        raise MLSegmentationError(
            f"Tecido '{tissue_key}' não é coberto pelo modelo '{model_key}'. "
            "Tecidos disponíveis: " + ", ".join(available_tissues("semi_auto") or ["nenhum"])
        )
    return predict_masks(model_key, image)[tissue_key]

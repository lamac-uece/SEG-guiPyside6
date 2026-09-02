"""
Registro dos modelos de segmentação automática disponíveis.

Cada entrada é um modelo ONNX (`onnxruntime.InferenceSession`) — pode ser
"binary" (1 canal, 1 tecido) ou "multiclass" (N canais, 1 tecido por canal,
na ordem de `tissues`). Hoje os dois modelos cadastrados são multiclasse,
cobrindo os mesmos 4 tecidos (imfat, muscle, scfat, vfat) — não há mais
nenhum modelo binário dedicado a um único tecido.

Os dois modos da UI usam modelos diferentes (ver MODE_MODEL): o modo
Semi-Auto (1 tecido por vez) usa o UNet simples, mais leve; o modo Auto
(lote, 4 tecidos de uma vez) usa o R2-Unet, mais pesado. Para o Semi-Auto,
`ml_segmentation.predict_mask` roda a inferência multiclasse completa e
extrai só o canal do tecido pedido — não existe atalho "binário" separado.

Para adicionar um novo modelo:
    1. Treine e exporte para ONNX (fora deste projeto — ver
       `ct-segmentation-unet/scripts/convert_to_onnx.py`).
    2. Copie o `.onnx` para `models/`.
    3. Adicione uma entrada em ML_TISSUE_MODELS abaixo (e em MODE_MODEL,
       se for para substituir/adicionar um modo).
Nenhum outro arquivo do projeto precisa ser tocado.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MLModelSpec:
    """Contrato de entrada/saída de um modelo de segmentação treinado."""

    model_path: str
    model_type: str = "binary"               # "binary" | "multiclass"
    input_size: int = 512
    threshold: float = 0.5
    tissues: tuple[str, ...] = ()            # canais em ordem -> tecidos (multiclass)
    conflict_priority: tuple[str, ...] = ()  # ordem de prioridade p/ sobreposição de canais


# Canais dos modelos multiclasse, na ordem de saída da rede (confirmado via
# NucleiDataGenerator.TISSUE_ORDER no repo de treino):
#   0=imfat -> "Intramuscular Fat" | 1=muscle -> "Muscle"
#   2=scfat -> "Fat"               | 3=vfat   -> "Visceral Fat"
_MULTICLASS_TISSUES = ("Intramuscular Fat", "Muscle", "Fat", "Visceral Fat")
_CONFLICT_PRIORITY = ("Muscle", "Fat", "Visceral Fat", "Intramuscular Fat")

ML_TISSUE_MODELS: dict[str, MLModelSpec] = {
    "UNet-Multiclasse": MLModelSpec(
        model_path="models/unet_all.onnx",
        model_type="multiclass",
        tissues=_MULTICLASS_TISSUES,
        conflict_priority=_CONFLICT_PRIORITY,
    ),
    "R2-Multiclasse": MLModelSpec(
        model_path="models/r2_unet_all.onnx",
        model_type="multiclass",
        tissues=_MULTICLASS_TISSUES,
        conflict_priority=_CONFLICT_PRIORITY,
    ),
}

# Mapeamento fixo modo -> modelo. Decisão de produto (não é escolha do
# usuário na UI): UNet simples é mais leve/rápido, então alimenta o modo
# interativo (Semi-Auto); R2-Unet é mais pesado/preciso, alimenta o modo
# em lote (Auto), rodado só uma vez por imagem.
MODE_MODEL: dict[str, str] = {
    "semi_auto": "UNet-Multiclasse",
    "auto": "R2-Multiclasse",
}


def registered_tissues() -> list[str]:
    """Tecidos cobertos por QUALQUER modelo do registro, independente de carregado."""
    seen: list[str] = []
    for spec in ML_TISSUE_MODELS.values():
        for tissue in spec.tissues:
            if tissue not in seen:
                seen.append(tissue)
    return seen

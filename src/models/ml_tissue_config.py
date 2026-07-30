"""
Registro dos modelos de segmentação automática disponíveis, indexados
pelo nome do tecido (mesma chave usada em `tissue_config.dictTissues`).

Cada entrada aponta para um arquivo `.keras` (modelo COMPLETO — arquitetura
+ pesos, salvo com `model.save(...)`, não `model.save_weights(...)`). Por
isso este arquivo nunca precisa saber nada sobre a arquitetura interna de
cada modelo: dois tecidos podem usar redes completamente diferentes (U-Net
comum, Attention ResU-Net, o que for) sem que nenhuma outra parte do
projeto precise mudar.

Para adicionar um novo tecido:
    1. Treine e valide o modelo (fora deste projeto).
    2. Salve com `model.save("nome.keras")` — não `save_weights`.
    3. Copie o arquivo para `models/`.
    4. Adicione uma linha em ML_TISSUE_MODELS abaixo.
Nenhum outro arquivo do projeto precisa ser tocado.

Só tecidos com modelo aqui registrado E carregado com sucesso (ver
`ml_segmentation.load_all_models`) aparecem para o usuário na hora de
escolher o tecido para segmentação automática.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MLModelSpec:
    """Contrato de entrada/saída de um modelo treinado para um tecido."""

    model_path: str
    input_size: int = 512
    threshold: float = 0.5


ML_TISSUE_MODELS: dict[str, MLModelSpec] = {
    "Fat": MLModelSpec(model_path="models/scfat.keras"),
    # Exemplo de como adicionar um novo tecido no futuro — só isso, mais nada:
    # "Muscle": MLModelSpec(model_path="models/muscle.keras"),
}


def registered_tissues() -> list[str]:
    """Tecidos cadastrados no registro (independente de terem carregado)."""
    return list(ML_TISSUE_MODELS.keys())
"""
Opções de aparência da malha (boundaries) do SuperPixel exibidas no painel
de Options. Centraliza as escolhas disponíveis para cor, grossura (modo do
contorno) e transparência da malha desenhada com `skimage.segmentation.mark_boundaries`.
"""

# ── Cores pré-definidas da malha ────────────────────────────────────────────
# Valores em formato RGB float (0.0–1.0), como esperado por mark_boundaries.
MESH_COLORS = {
    "Blue (recommended)": (0.0, 0.0, 1.0),
    "Yellow":             (1.0, 1.0, 0.0),
    "Red":                (1.0, 0.0, 0.0),
    "Green":              (0.0, 1.0, 0.0),
    "Cyan":               (0.0, 1.0, 1.0),
    "Magenta":            (1.0, 0.0, 1.0),
    "White":              (1.0, 1.0, 1.0),
    "Orange":             (1.0, 0.5, 0.0),
}

# ── Grossura da malha ────────────────────────────────────────────────────────
# Corresponde ao parâmetro `mode` de mark_boundaries, que controla como o
# contorno de cada superpixel é desenhado sobre a imagem.
#   outer -> contorno fino, por fora da borda do segmento (recomendado)
#   inner -> contorno fino, por dentro da borda do segmento
#   thick -> contorno mais grosso (mais visível, porém menos preciso)
#
# IMPORTANTE: 'subpixel' foi removido de propósito das opções selecionáveis.
# Esse modo dobra a resolução da imagem exibida (é assim que o algoritmo do
# skimage funciona, não é uma escolha nossa de renderização). Como o clique
# de pintura (paint_superpixel) usa as coordenadas da imagem EXIBIDA para
# indexar em `segments_global`, que continua na resolução ORIGINAL, isso faz
# com que o clique acerte o tecido errado (deslocado) ou até trave o app perto
# das bordas. outer/inner/thick preservam exatamente a resolução original da
# imagem e por isso não têm esse risco — só eles são seguros para pintura.
UNSAFE_MESH_MODES = {"subpixel"}

MESH_MODES = {
    "Thin (outer, recommended)": "outer",
    "Inner":                     "inner",
    "Thick":                     "thick",
}

# ── Transparência (opacidade) pré-definida da malha ─────────────────────────
# 1.0 = 100% opaca, valores menores deixam a malha mais transparente sobre a
# imagem/máscara. 75% é o valor recomendado (bom equilíbrio entre visibilidade
# do contorno e preservação da textura exatamente em cima da linha).
MESH_OPACITIES = {
    "100% (opaque)":     1.0,
    "75% (recommended)": 0.75,
    "50%":               0.5,
    "25%":               0.25,
}
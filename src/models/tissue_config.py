import numpy as np

from src.models.mesh_config import MESH_COLORS

colors = {
    'black':  [(0,0,0),       0],
    'white':  [(255,255,255), 1],
    'red':    [(255,0,0),     2],
    'green':  [(0,255,0),     3],
    'blue':   [(0,0,255),     4],
    'yellow': [(255,255,0),   5],
    'orange': [(255,140,0),   6],
    'gray':   [(127,127,127), 9]
}

"""
HU range for each material
'material': [(minimum value, maximum value), 'color']
Although 'muscle' minimum value should be 31 (and not -29).
this helps in the segmentation process
"""
materials = {
    'bone':         [(   500, 10000), 'white' ],
    'bonelike':     [(   160, 10000), 'white' ],
    'muscle':       [(   -29,   150), 'orange'], #'muscle': [(31, 150), 'blue'],
    'skmuscle':     [(    10,    40), 'red'   ],
    'organ':        [(   -29,    30), 'green' ],
    'musclelike':   [(   -50,   150), 'orange'], # includes part of subcutaneous fat
    'fat':          [(  -190,   -30), 'yellow'], 
    'scfat':        [(  -190,   -30), 'blue'  ], # subcutaneous fat
    'imfat':        [(  -150,   -50), 'green' ], # visceral fat (ver e-mail da Sara)
    'fatlike':      [(  -190,   -10), 'yellow'], # fat with a bit of muscle
    'air':          [(-10000,  -300), 'black' ]
}

dictTissues = {
    "Fat":1,
    "Intermuscular Fat":2, 
    "Visceral Fat":3, 
    "Bone":4, 
    "Muscle":5, 
    "Organ":6, 
    "Other": 7
}

def _mesh_rgb255(color_name: str) -> np.ndarray:
    """Converte uma cor da paleta da malha (float 0–1) para RGB 0–255."""
    rgb = MESH_COLORS[color_name]
    return np.array([round(c * 255) for c in rgb])

"""
Cor padrão atribuída automaticamente quando um tecido é criado.
Baseada na paleta padrão da malha (MESH_COLORS). Tecidos ausentes deste
mapeamento não possuem cor padrão (None em default_tissue_color).
"""
DEFAULT_TISSUE_COLORS = {
    "Fat":              _mesh_rgb255("Cyan"),
    "Intermuscular Fat": _mesh_rgb255("Green"),
    "Visceral Fat":      _mesh_rgb255("Yellow"),
    "Muscle":            _mesh_rgb255("Red"),
}

# Cor usada como fallback para tecidos sem cor padrão (ex.: Bone, Organ, Other).
FALLBACK_COLOR = np.array([255, 255, 0])

# Tecidos exibidos na paleta de seleção da interface (ordem de exibição).
DEFAULT_TISSUES = (
    "Fat",
    "Intermuscular Fat",
    "Visceral Fat",
    "Muscle",
)

def default_tissue_color(tissue_name: str):
    """Retorna a cor padrão (np.array RGB 0–255) do tecido, ou None se não houver."""
    return DEFAULT_TISSUE_COLORS.get(tissue_name)

COLORS = [
    '#ffeeb9',
    '#bd4b4b',
    '#442242',
    '#1ab11d',
    '#286440',
    '#133542',
    '#675c85',
    '#251e3c',
    '#1e132c',
    '#b5b4d3',
    '#6b6a7c',
    '#232328'
]
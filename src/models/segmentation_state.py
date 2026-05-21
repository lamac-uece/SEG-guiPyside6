from dataclasses import dataclass, field
import numpy as np
from src.services.undo_manager import UndoStack

@dataclass
class SegmentationState:

    # ── arquivo ───────────────────────────────────────────────────────────────
    file_name: str = ""
    file_name_global: str = ""
    
    csv_flag: bool = False
    save_dir: str = ""
    open_dir: str = ""

    # ── imagem ────────────────────────────────────────────────────────────────
    dicom_image_array: list = field(default_factory=list)
    area: int = 1
    graph: str = ""

    # ── segmentação ───────────────────────────────────────────────────────────
    segments_global: list = field(default_factory=list)
    segmented_mask: list = field(default_factory=list)
    mask3d: list = field(default_factory=list)
    masks: list = field(default_factory=list)
    masks_empty: bool = True

    # ── tecidos e cores ───────────────────────────────────────────────────────
    current_tissue: int = 0
    colorvec: object = field(
        default_factory=lambda: np.array([255, 255, 0])
    )
    informacoes: dict = field(
        default_factory=lambda: {
            "colors": [], "identifier": [], "tissue": []
        }
    )
    fat_hu: list = field(default_factory=list)
    muscle_hu: list = field(default_factory=list)
    selected_hu: list = field(default_factory=list)

    # ── pintura e undo ────────────────────────────────────────────────────────
    previous_paints: list = field(default_factory=list)
    previous_segments: dict = field(
        default_factory=lambda: {
            "superpixel": [], "previous_identifier": []
        }
    )
    superpixel_auth: bool = False
    undo: int = 0
    undo_stack: UndoStack = field(default_factory=UndoStack)

    # ── parâmetros SLIC ───────────────────────────────────────────────────────
    num_segments: int = 2000
    sigma_slic: int = 1
    compactness: float = 0.05
    max_num_iter: int = 10
    min_size_factor: float = 0.5
    max_size_factor: float = 3.0
    multiplicator: float = 1.0

    # ── parâmetros CLAHE ──────────────────────────────────────────────────────
    clip_limit: float = 0.03
    nbins: int = 256

    # ── UI ────────────────────────────────────────────────────────────────────
    current_plot: int = 0
    show_superpixel: bool = True
    toggle_available: bool = False
    radio_density_check_enabled: bool = True
import numpy as np

from src.models.mesh_config import MESH_COLORS
from src.models.tissue_config import (
    DEFAULT_TISSUES,
    DEFAULT_TISSUE_COLORS,
    FALLBACK_COLOR,
    default_tissue_color,
    dictTissues,
)


def test_default_tissue_colors_rgb():
    assert np.array_equal(default_tissue_color("Fat"),
                          np.array([0, 255, 255]))
    assert np.array_equal(default_tissue_color("Intermuscular Fat"),
                          np.array([0, 255, 0]))
    assert np.array_equal(default_tissue_color("Visceral Fat"),
                          np.array([255, 255, 0]))
    assert np.array_equal(default_tissue_color("Muscle"),
                          np.array([255, 0, 0]))


def test_tissues_without_default_return_none():
    for name in ("Bone", "Organ", "Other"):
        assert default_tissue_color(name) is None


def test_fallback_color_is_yellow():
    assert np.array_equal(FALLBACK_COLOR, np.array([255, 255, 0]))


def test_dict_tissues_uses_intermuscular_name():
    assert "Intermuscular Fat" in dictTissues
    assert dictTissues["Intermuscular Fat"] == 2
    assert "Intramuscular Fat" not in dictTissues


def test_default_colors_derived_from_mesh_palette():
    expected = {
        "Fat":               tuple(round(c * 255) for c in MESH_COLORS["Cyan"]),
        "Intermuscular Fat": tuple(round(c * 255) for c in MESH_COLORS["Green"]),
        "Visceral Fat":      tuple(round(c * 255) for c in MESH_COLORS["Yellow"]),
        "Muscle":            tuple(round(c * 255) for c in MESH_COLORS["Red"]),
    }
    assert set(DEFAULT_TISSUE_COLORS) == set(expected)
    for name, color in DEFAULT_TISSUE_COLORS.items():
        assert tuple(color) == expected[name]


def test_default_tissues_order():
    assert DEFAULT_TISSUES == (
        "Fat",
        "Intermuscular Fat",
        "Visceral Fat",
        "Muscle",
    )


def test_all_default_tissues_have_color():
    for name in DEFAULT_TISSUES:
        assert default_tissue_color(name) is not None

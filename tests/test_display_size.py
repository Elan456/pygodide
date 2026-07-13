from pathlib import Path

import pytest

from pygodide.builder.display_size import detect_display_size
from pygodide.builder.plan import resolve_canvas_size
from pygodide.project_config import PygodideProjectConfig


def test_detect_display_size_from_literal_set_mode(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "import pygame\npygame.display.set_mode((1024, 768))\n",
        encoding="utf-8",
    )

    result = detect_display_size(
        tmp_path, entry_module="main", package_files=["main.py"]
    )
    assert result.found is True
    assert result.source == "main.py"
    assert (result.width, result.height) == (1024, 768)


def test_detect_display_size_from_named_constants(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        """
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720
import pygame
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
""".lstrip(),
        encoding="utf-8",
    )

    result = detect_display_size(
        tmp_path, entry_module="main", package_files=["main.py"]
    )
    assert result.found is True
    assert result.source == "main.py"
    assert (result.width, result.height) == (1280, 720)


def test_detect_display_size_falls_back_to_default(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "async def main():\n    return None\n",
        encoding="utf-8",
    )

    result = detect_display_size(
        tmp_path, entry_module="main", package_files=["main.py"]
    )
    assert result.found is False
    assert result.source is None
    assert (result.width, result.height) == (800, 600)


def test_resolve_canvas_size_defaults_to_fixed_discovered() -> None:
    width, height, layout = resolve_canvas_size(
        None,
        detected_width=1024,
        detected_height=576,
    )
    assert (width, height, layout) == (1024, 576, "fixed")


def test_resolve_canvas_size_fit() -> None:
    width, height, layout = resolve_canvas_size(
        None,
        canvas_fit=True,
        detected_width=800,
        detected_height=600,
    )
    assert (width, height, layout) == (800, 600, "fit")


def test_resolve_canvas_size_fill() -> None:
    width, height, layout = resolve_canvas_size(
        None,
        canvas_fill=True,
        detected_width=800,
        detected_height=600,
    )
    assert (width, height, layout) == (800, 600, "fill")


def test_resolve_canvas_size_fixed_from_cli() -> None:
    width, height, layout = resolve_canvas_size(
        None,
        canvas_width=1280,
        canvas_height=720,
        detected_width=800,
        detected_height=600,
    )
    assert (width, height, layout) == (1280, 720, "fixed")


def test_resolve_canvas_size_fit_with_explicit_aspect() -> None:
    width, height, layout = resolve_canvas_size(
        None,
        canvas_width=960,
        canvas_height=540,
        canvas_fit=True,
        detected_width=800,
        detected_height=600,
    )
    assert (width, height, layout) == (960, 540, "fit")


def test_resolve_canvas_size_fill_with_explicit_reference_size() -> None:
    width, height, layout = resolve_canvas_size(
        None,
        canvas_width=960,
        canvas_height=540,
        canvas_fill=True,
        detected_width=800,
        detected_height=600,
    )
    assert (width, height, layout) == (960, 540, "fill")


def test_resolve_canvas_size_rejects_fit_and_fill() -> None:
    with pytest.raises(ValueError, match="Cannot combine canvas-fit and canvas-fill"):
        resolve_canvas_size(
            None,
            canvas_fit=True,
            canvas_fill=True,
        )


def test_resolve_canvas_size_project_fit() -> None:
    config = PygodideProjectConfig(canvas_fit=True)
    width, height, layout = resolve_canvas_size(
        config,
        detected_width=640,
        detected_height=480,
    )
    assert (width, height, layout) == (640, 480, "fit")

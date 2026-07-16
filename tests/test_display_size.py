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


def test_ignores_one_by_one_noframe_in_unrelated_root_file(tmp_path: Path) -> None:
    """Batch/forge helpers often open a 1x1 NOFRAME surface for convert()."""
    (tmp_path / "main.py").write_text(
        """
import pygame
SCREEN_WIDTH, SCREEN_HEIGHT = 960, 540

async def main():
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
""".lstrip(),
        encoding="utf-8",
    )
    (tmp_path / "batch_forge.py").write_text(
        """
import pygame

def run_batch_forge() -> None:
    pygame.init()
    # Initialize a hidden display to allow surface conversion
    pygame.display.set_mode((1, 1), pygame.NOFRAME)
""".lstrip(),
        encoding="utf-8",
    )

    result = detect_display_size(
        tmp_path,
        entry_module="main",
        package_files=["batch_forge.py", "main.py"],
    )
    assert result.found is True
    assert result.source == "main.py"
    assert (result.width, result.height) == (960, 540)


def test_ignores_dummy_when_only_other_files_have_playable_size(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.py").write_text(
        "async def main():\n    return None\n",
        encoding="utf-8",
    )
    (tmp_path / "util.py").write_text(
        "import pygame\npygame.display.set_mode((1, 1), pygame.NOFRAME)\n",
        encoding="utf-8",
    )
    (tmp_path / "game" / "window.py").parent.mkdir()
    (tmp_path / "game" / "window.py").write_text(
        "import pygame\npygame.display.set_mode((640, 480))\n",
        encoding="utf-8",
    )

    result = detect_display_size(
        tmp_path,
        entry_module="main",
        package_files=["main.py", "util.py", "game/window.py"],
    )
    assert result.found is True
    assert result.source == "game/window.py"
    assert (result.width, result.height) == (640, 480)


def test_only_dummy_sizes_falls_back_to_default(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "import pygame\npygame.display.set_mode((1, 1), pygame.NOFRAME)\n",
        encoding="utf-8",
    )

    result = detect_display_size(
        tmp_path, entry_module="main", package_files=["main.py"]
    )
    assert result.found is False
    assert result.source is None
    assert (result.width, result.height) == (800, 600)


def test_entry_module_preferred_over_larger_size_elsewhere(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "import pygame\npygame.display.set_mode((800, 600))\n",
        encoding="utf-8",
    )
    (tmp_path / "menu.py").write_text(
        "import pygame\npygame.display.set_mode((1920, 1080))\n",
        encoding="utf-8",
    )

    result = detect_display_size(
        tmp_path,
        entry_module="main",
        package_files=["menu.py", "main.py"],
    )
    assert result.found is True
    assert result.source == "main.py"
    assert (result.width, result.height) == (800, 600)


def test_within_entry_prefers_playable_over_preceding_dummy(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.py").write_text(
        """
import pygame
pygame.display.set_mode((1, 1), pygame.NOFRAME)
screen = pygame.display.set_mode((1024, 768))
""".lstrip(),
        encoding="utf-8",
    )

    result = detect_display_size(
        tmp_path, entry_module="main", package_files=["main.py"]
    )
    assert result.found is True
    assert (result.width, result.height) == (1024, 768)


def test_same_directory_as_entry_preferred_over_distant_file(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.py").write_text(
        "async def main():\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "display.py").write_text(
        "import pygame\npygame.display.set_mode((800, 600))\n",
        encoding="utf-8",
    )
    (tmp_path / "vendor" / "big.py").parent.mkdir()
    (tmp_path / "vendor" / "big.py").write_text(
        "import pygame\npygame.display.set_mode((2560, 1440))\n",
        encoding="utf-8",
    )

    result = detect_display_size(
        tmp_path,
        entry_module="main",
        package_files=["main.py", "vendor/big.py", "display.py"],
    )
    assert result.found is True
    assert result.source == "display.py"
    assert (result.width, result.height) == (800, 600)


def test_hidden_keyword_flag_marks_small_surface_dummy(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text(
        "import pygame\npygame.display.set_mode((800, 600))\n",
        encoding="utf-8",
    )
    (tmp_path / "tools.py").write_text(
        "import pygame\npygame.display.set_mode((64, 64), flags=pygame.HIDDEN)\n",
        encoding="utf-8",
    )

    result = detect_display_size(
        tmp_path,
        entry_module="main",
        package_files=["tools.py", "main.py"],
    )
    assert result.source == "main.py"
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

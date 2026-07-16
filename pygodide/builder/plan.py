from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from pygodide.builder.display_size import (
    DEFAULT_DISPLAY_HEIGHT,
    DEFAULT_DISPLAY_WIDTH,
    DisplaySizeDetection,
    detect_display_size,
)
from pygodide.project_config import (
    AppEntrypoint,
    PygodideProjectConfig,
    load_pygodide_project_config,
    parse_app_spec,
)

DEFAULT_APP_SPEC = "main:main"
DEFAULT_CANVAS_WIDTH = DEFAULT_DISPLAY_WIDTH
DEFAULT_CANVAS_HEIGHT = DEFAULT_DISPLAY_HEIGHT
DEFAULT_PYTHON_PATH_ENTRIES = ["/"]
DEFAULT_RELATIVE_PYTHON_PATH_ENTRIES = ["."]
DEFAULT_EXCLUDED_FILENAMES = {"pyproject.toml", "testing_manifest.yaml", "uv.lock"}
# Directory names skipped anywhere in a relative path during auto-discovery.
IGNORED_PATH_PARTS = {
    ".git",
    ".github",
    ".gitlab",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    "build",
    "node_modules",
}

# fixed: exact pixel box (default = auto-discovered set_mode size as-is)
# fit: largest size in the viewport that keeps the game aspect ratio
# fill: stretch to the full viewport (may change aspect)
CanvasLayout = Literal["fit", "fill", "fixed"]


@dataclass(frozen=True)
class BuildPlan:
    source_dir: Path
    output_dir: Path
    package_files: list[str]
    entry_module: str
    entry_function: str
    app_source: str
    package_files_source: str
    title: str
    # Layout box size (always set). For fit/fill this is the game aspect size;
    # for fixed it is the discovered or configured pixel box.
    canvas_width: int
    canvas_height: int
    canvas_layout: CanvasLayout
    # Result of set_mode scanning (fallback 800x600 when not found).
    canvas_aspect_found: bool
    canvas_aspect_source: str | None
    canvas_aspect_width: int
    canvas_aspect_height: int
    python_path_entries: list[str]


def looks_like_pygodide_output_dir(path: str | Path) -> bool:
    """True when PATH looks like a previous ``pygodide build`` output.

    Detected by the presence of generated ``index.html`` + ``boot.js``, not
    merely a directory named ``build`` (a game project may be named that).
    """
    resolved = Path(path).resolve()
    if not resolved.is_dir():
        return False
    return (resolved / "boot.js").is_file() and (resolved / "index.html").is_file()


def build_directory_warning_message(source_dir: Path) -> str:
    project_root = source_dir.parent if source_dir.name == "build" else source_dir
    return (
        f"{source_dir} looks like a previous pygodide build output "
        "(found index.html + boot.js).\n"
        "You usually want to build from the game project root (the folder with "
        "your source), not from inside build/.\n"
        f"If that was unintentional, try:  cd {project_root} && pygodide build .\n"
        "If this directory really is your project root, you can ignore this warning."
    )


def warn_if_pygodide_output_dir(
    source_dir: str | Path,
    *,
    log: Callable[[str], None] | None = None,
) -> bool:
    """Log a warning when SOURCE_DIR looks like build output. Never raises."""
    resolved = Path(source_dir).resolve()
    if not looks_like_pygodide_output_dir(resolved):
        return False
    message = f"Warning: {build_directory_warning_message(resolved)}"
    if log is not None:
        log(message)
    return True


def build_plan_for_source(
    source_dir: str | Path,
    *,
    app_spec: str | None = None,
    canvas_width: int | None = None,
    canvas_height: int | None = None,
    canvas_fit: bool | None = None,
    canvas_fill: bool | None = None,
) -> BuildPlan:
    resolved_source_dir = Path(source_dir).resolve()
    if not resolved_source_dir.is_dir():
        raise ValueError(f"{resolved_source_dir} is not a directory")

    project_config = load_pygodide_project_config(resolved_source_dir)
    resolved_app, app_source = _resolve_app_entrypoint(
        project_config, app_spec=app_spec
    )
    package_files = discover_package_files(
        resolved_source_dir,
        include_patterns=project_config.include if project_config else None,
    )
    if not package_files:
        raise ValueError(f"{resolved_source_dir} does not contain any files to build")

    _require_entry_module_file(
        resolved_source_dir,
        entry_module=resolved_app.module,
        package_files=package_files,
        app_source=app_source,
    )

    raw_python_path_entries = (
        project_config.python_path
        if project_config and project_config.python_path
        else DEFAULT_RELATIVE_PYTHON_PATH_ENTRIES
    )
    detection: DisplaySizeDetection = detect_display_size(
        resolved_source_dir,
        entry_module=resolved_app.module,
        package_files=package_files,
    )
    resolved_width, resolved_height, canvas_layout = resolve_canvas_size(
        project_config,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        canvas_fit=canvas_fit,
        canvas_fill=canvas_fill,
        detected_width=detection.width,
        detected_height=detection.height,
    )

    return BuildPlan(
        source_dir=resolved_source_dir,
        output_dir=build_output_dir(resolved_source_dir),
        package_files=package_files,
        entry_module=resolved_app.module,
        entry_function=resolved_app.callable_name,
        app_source=app_source,
        package_files_source=(
            "[tool.pygodide].include"
            if project_config and project_config.include
            else "auto-discovery"
        ),
        title=(
            project_config.title
            if project_config and project_config.title
            else default_title(resolved_source_dir)
        ),
        canvas_width=resolved_width,
        canvas_height=resolved_height,
        canvas_layout=canvas_layout,
        canvas_aspect_found=detection.found,
        canvas_aspect_source=detection.source,
        canvas_aspect_width=detection.width,
        canvas_aspect_height=detection.height,
        python_path_entries=resolve_python_path_entries(raw_python_path_entries),
    )


def resolve_canvas_size(
    project_config: PygodideProjectConfig | None,
    *,
    canvas_width: int | None = None,
    canvas_height: int | None = None,
    canvas_fit: bool | None = None,
    canvas_fill: bool | None = None,
    detected_width: int = DEFAULT_CANVAS_WIDTH,
    detected_height: int = DEFAULT_CANVAS_HEIGHT,
) -> tuple[int, int, CanvasLayout]:
    """Resolve canvas layout and reference size.

    Layout modes (fit and fill are mutually exclusive):
    - Default: fixed box at auto-discovered ``set_mode`` size (as-is)
    - ``canvas-width`` / ``canvas-height`` alone: fixed box at that size
    - ``canvas-fit``: largest viewport size keeping aspect; size from width/height
      when set, otherwise from discovery (for when ``set_mode`` is not found)
    - ``canvas-fill``: stretch to fill the viewport; optional width/height only
      set the pre-stretch reference size

    Discovery falls back to 800×600 when ``set_mode`` cannot be resolved.
    """
    width = (
        canvas_width
        if canvas_width is not None
        else (
            project_config.canvas_width
            if project_config and project_config.canvas_width is not None
            else None
        )
    )
    height = (
        canvas_height
        if canvas_height is not None
        else (
            project_config.canvas_height
            if project_config and project_config.canvas_height is not None
            else None
        )
    )
    fit = (
        canvas_fit
        if canvas_fit is not None
        else (
            project_config.canvas_fit
            if project_config and project_config.canvas_fit is not None
            else None
        )
    )
    fill = (
        canvas_fill
        if canvas_fill is not None
        else (
            project_config.canvas_fill
            if project_config and project_config.canvas_fill is not None
            else None
        )
    )

    wants_fit = fit is True
    wants_fill = fill is True
    if wants_fit and wants_fill:
        raise ValueError(
            "Cannot combine canvas-fit and canvas-fill. "
            "Use fit (aspect-preserving scale), fill (stretch), or a fixed size."
        )

    game_width = DEFAULT_CANVAS_WIDTH if detected_width <= 0 else detected_width
    game_height = DEFAULT_CANVAS_HEIGHT if detected_height <= 0 else detected_height
    has_configured_size = width is not None or height is not None
    reference_width = game_width if width is None else width
    reference_height = game_height if height is None else height
    if reference_width <= 0 or reference_height <= 0:
        raise ValueError(
            f"Canvas size must be positive (got {reference_width}x{reference_height})"
        )

    if wants_fit:
        # Width/height (when set) supply the aspect ratio for viewport scaling.
        return reference_width, reference_height, "fit"

    if wants_fill:
        return reference_width, reference_height, "fill"

    if has_configured_size:
        return reference_width, reference_height, "fixed"

    # Default: use auto-discovered size as a fixed pixel box.
    return game_width, game_height, "fixed"


def build_output_dir(path: str | Path) -> Path:
    """Return the directory that holds (or will hold) build output.

    - Project roots → ``<project>/build``
    - An existing pygodide output tree (has ``index.html`` + ``boot.js``) → itself
      (so ``pygodide serve path/to/build`` works)
    - A project whose directory is literally named ``build`` → ``build/build``
    """
    resolved_path = Path(path).resolve()
    if looks_like_pygodide_output_dir(resolved_path):
        return resolved_path
    return resolved_path / "build"


def clean_build_dir(path: str | Path) -> Path:
    output_dir = build_output_dir(path)
    # Never delete the source tree when source and output are the same path
    # (e.g. user pointed build at a previous output directory).
    if output_dir.resolve() == Path(path).resolve() and looks_like_pygodide_output_dir(
        output_dir
    ):
        return output_dir
    if output_dir.exists():
        shutil.rmtree(output_dir)
    return output_dir


def copy_package_files(
    *, source_dir: str | Path, output_dir: str | Path, package_files: list[str]
) -> None:
    resolved_source_dir = Path(source_dir).resolve()
    resolved_output_dir = Path(output_dir).resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    for relative_path in package_files:
        source_path = resolved_source_dir / relative_path
        destination_path = resolved_output_dir / relative_path
        if source_path.resolve() == destination_path.resolve():
            # Building with source == output (unusual); skip no-op copies.
            continue
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)


def discover_package_files(
    source_dir: str | Path, *, include_patterns: list[str] | None = None
) -> list[str]:
    resolved_source_dir = Path(source_dir).resolve()
    discovered_files: set[str] = set()

    if include_patterns:
        for pattern in include_patterns:
            pattern_matches: set[str] = set()
            for path in _iter_include_matches(resolved_source_dir, pattern):
                if not path.is_file():
                    continue

                relative_path = path.relative_to(resolved_source_dir)
                if _should_ignore_path(relative_path):
                    continue

                relative_posix_path = relative_path.as_posix()
                pattern_matches.add(relative_posix_path)
                discovered_files.add(relative_posix_path)

            if not pattern_matches:
                raise ValueError(
                    f"Include pattern {pattern!r} matched no files in "
                    f"{resolved_source_dir}"
                )
    else:
        for path in resolved_source_dir.rglob("*"):
            if not path.is_file():
                continue

            relative_path = path.relative_to(resolved_source_dir)
            if _should_ignore_path(relative_path):
                continue
            if path.name in DEFAULT_EXCLUDED_FILENAMES:
                continue

            discovered_files.add(relative_path.as_posix())

    return sorted(discovered_files)


def default_title(source_dir: Path) -> str:
    if source_dir.name == "src" and source_dir.parent.name:
        return f"{source_dir.parent.name} Pyodide App"
    return f"{source_dir.name} Pyodide App"


def resolve_python_path_entries(
    entries: list[str], *, virtual_fs_root: str = "/"
) -> list[str]:
    normalized_root = _normalize_virtual_path(virtual_fs_root)
    resolved_entries: list[str] = []

    for entry in entries:
        if entry.startswith("/"):
            resolved_entry = _normalize_virtual_path(entry)
        else:
            resolved_entry = _normalize_virtual_path(
                str(PurePosixPath(normalized_root) / entry)
            )

        if resolved_entry not in resolved_entries:
            resolved_entries.append(resolved_entry)

    return resolved_entries or DEFAULT_PYTHON_PATH_ENTRIES.copy()


def _resolve_app_entrypoint(
    project_config: PygodideProjectConfig | None, *, app_spec: str | None
) -> tuple[AppEntrypoint, str]:
    resolved_spec = app_spec
    if resolved_spec is not None:
        return parse_app_spec(resolved_spec), "CLI --app"
    if project_config and project_config.app is not None:
        return project_config.app, "[tool.pygodide].app"
    if resolved_spec is None:
        resolved_spec = DEFAULT_APP_SPEC
    return parse_app_spec(resolved_spec), "default"


def entry_module_relative_path(entry_module: str) -> str:
    """Relative path of the Python file for an importable entry module."""
    return f"{entry_module.replace('.', '/')}.py"


def _require_entry_module_file(
    source_dir: Path,
    *,
    entry_module: str,
    package_files: list[str],
    app_source: str,
) -> None:
    """Fail the plan when the entry module is not among staged package files."""
    relative_path = entry_module_relative_path(entry_module)
    if relative_path in package_files:
        return

    on_disk = (source_dir / relative_path).is_file()
    if on_disk:
        raise ValueError(
            f"Entry module file {relative_path!r} exists but is not included in "
            f"the build package (entrypoint {entry_module!r} from {app_source}). "
            "Add it via [tool.pygodide].include, or stop excluding it."
        )
    raise ValueError(
        f"Entry module file {relative_path!r} not found under {source_dir} "
        f"(entrypoint {entry_module!r} from {app_source}). "
        "Create that file or set --app / [tool.pygodide].app to module:callable."
    )


def _normalize_virtual_path(path: str) -> str:
    normalized = str(PurePosixPath(path))
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized


def _should_ignore_path(relative_path: Path) -> bool:
    return any(part in IGNORED_PATH_PARTS for part in relative_path.parts)


def _iter_include_matches(source_dir: Path, pattern: str):
    normalized_pattern = pattern.rstrip("/")
    if normalized_pattern == "**":
        yield from source_dir.rglob("*")
        return

    if normalized_pattern.endswith("/**"):
        relative_root = normalized_pattern[:-3]
        search_root = source_dir / relative_root if relative_root else source_dir
        if search_root.exists():
            yield from search_root.rglob("*")
        return

    yield from source_dir.glob(pattern)

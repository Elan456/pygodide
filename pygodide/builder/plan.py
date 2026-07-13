from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pygodide.project_config import (
    AppEntrypoint,
    PygodideProjectConfig,
    load_pygodide_project_config,
    parse_app_spec,
)

DEFAULT_APP_SPEC = "main:main"
DEFAULT_CANVAS_WIDTH = 800
DEFAULT_CANVAS_HEIGHT = 600
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
    # None means fill the browser viewport at boot time.
    canvas_width: int | None
    canvas_height: int | None
    python_path_entries: list[str]


def build_plan_for_source(
    source_dir: str | Path,
    *,
    app_spec: str | None = None,
    canvas_width: int | None = None,
    canvas_height: int | None = None,
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

    raw_python_path_entries = (
        project_config.python_path
        if project_config and project_config.python_path
        else DEFAULT_RELATIVE_PYTHON_PATH_ENTRIES
    )
    resolved_width, resolved_height = resolve_canvas_size(
        project_config,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
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
        python_path_entries=resolve_python_path_entries(raw_python_path_entries),
    )


def resolve_canvas_size(
    project_config: PygodideProjectConfig | None,
    *,
    canvas_width: int | None = None,
    canvas_height: int | None = None,
) -> tuple[int | None, int | None]:
    """Resolve canvas size.

    Priority: CLI overrides project config. If neither side is set for either
    dimension, return ``(None, None)`` so the browser fills the viewport.
    If only one dimension is set, the other falls back to the fixed defaults.
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
    if width is None and height is None:
        return None, None

    resolved_width = DEFAULT_CANVAS_WIDTH if width is None else width
    resolved_height = DEFAULT_CANVAS_HEIGHT if height is None else height
    if resolved_width <= 0 or resolved_height <= 0:
        raise ValueError(
            f"Canvas size must be positive (got {resolved_width}x{resolved_height})"
        )
    return resolved_width, resolved_height


def build_output_dir(path: str | Path) -> Path:
    resolved_path = Path(path).resolve()
    if resolved_path.name == "build":
        return resolved_path
    return resolved_path / "build"


def clean_build_dir(path: str | Path) -> Path:
    output_dir = build_output_dir(path)
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

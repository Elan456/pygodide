"""Detect pygame display size from source for canvas aspect fitting."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DISPLAY_WIDTH = 800
DEFAULT_DISPLAY_HEIGHT = 600


@dataclass(frozen=True)
class DisplaySizeDetection:
    """Result of scanning for ``pygame.display.set_mode`` dimensions."""

    width: int
    height: int
    found: bool
    # Relative package path when found (e.g. ``main.py``); None on fallback.
    source: str | None = None


def detect_display_size(
    source_dir: Path,
    *,
    entry_module: str,
    package_files: list[str],
) -> DisplaySizeDetection:
    """Best-effort width/height from ``pygame.display.set_mode``.

    Prefers the entrypoint module, then other staged ``.py`` files. Falls back
    to ``800x600`` when nothing is found or values cannot be resolved.
    """
    candidates = _python_files_for_detection(
        source_dir,
        entry_module=entry_module,
        package_files=package_files,
    )
    for relative_path, path in candidates:
        size = _display_size_from_file(path)
        if size is not None:
            width, height = size
            return DisplaySizeDetection(
                width=width,
                height=height,
                found=True,
                source=relative_path,
            )
    return DisplaySizeDetection(
        width=DEFAULT_DISPLAY_WIDTH,
        height=DEFAULT_DISPLAY_HEIGHT,
        found=False,
        source=None,
    )


def _python_files_for_detection(
    source_dir: Path,
    *,
    entry_module: str,
    package_files: list[str],
) -> list[tuple[str, Path]]:
    entry_relative = f"{entry_module.replace('.', '/')}.py"
    ordered: list[str] = []
    if entry_relative in package_files:
        ordered.append(entry_relative)
    for relative in package_files:
        if relative.endswith(".py") and relative not in ordered:
            ordered.append(relative)

    paths: list[tuple[str, Path]] = []
    for relative in ordered:
        path = source_dir / relative
        if path.is_file():
            paths.append((relative, path))
    return paths


def _display_size_from_file(path: Path) -> tuple[int, int] | None:
    try:
        source = path.read_text(encoding="utf-8")
        module = ast.parse(source, filename=str(path))
    except OSError, SyntaxError, UnicodeError:
        return None

    constants = _module_int_constants(module)
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        if not _is_set_mode_call(node):
            continue
        size = _size_from_set_mode_call(node, constants)
        if size is not None:
            return size
    return None


def _is_set_mode_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "set_mode":
        return True
    return isinstance(func, ast.Name) and func.id == "set_mode"


def _size_from_set_mode_call(
    node: ast.Call, constants: dict[str, int]
) -> tuple[int, int] | None:
    if not node.args:
        return None

    first = node.args[0]
    if isinstance(first, ast.Tuple) and len(first.elts) >= 2:
        width = _resolve_int(first.elts[0], constants)
        height = _resolve_int(first.elts[1], constants)
        if width is not None and height is not None and width > 0 and height > 0:
            return width, height
        return None

    if len(node.args) >= 2:
        width = _resolve_int(node.args[0], constants)
        height = _resolve_int(node.args[1], constants)
        if width is not None and height is not None and width > 0 and height > 0:
            return width, height
    return None


def _module_int_constants(module: ast.Module) -> dict[str, int]:
    constants: dict[str, int] = {}
    for statement in module.body:
        if not isinstance(statement, ast.Assign):
            continue
        value = statement.value
        if isinstance(value, ast.Constant) and isinstance(value.value, int):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = value.value
            continue
        if isinstance(value, ast.Tuple) and all(
            isinstance(elt, ast.Constant) and isinstance(elt.value, int)
            for elt in value.elts
        ):
            for target in statement.targets:
                if not isinstance(target, ast.Tuple):
                    continue
                if len(target.elts) != len(value.elts):
                    continue
                for name_node, elt in zip(target.elts, value.elts, strict=True):
                    if isinstance(name_node, ast.Name) and isinstance(
                        elt, ast.Constant
                    ):
                        constants[name_node.id] = int(elt.value)
    return constants


def _resolve_int(node: ast.AST, constants: dict[str, int]) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        value = _resolve_int(node.operand, constants)
        return -value if value is not None else None
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    return None

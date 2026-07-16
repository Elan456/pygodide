"""Detect pygame display size from source for canvas aspect fitting.

Scans staged Python for ``pygame.display.set_mode`` (and bare ``set_mode``)
calls, then picks a **playable** size rather than the first hit in the tree.

Dummy surfaces (``(1, 1)`` + ``NOFRAME`` headless helpers, etc.) are ignored so
unrelated utilities in the project root do not become the HTML canvas size.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

DEFAULT_DISPLAY_WIDTH = 800
DEFAULT_DISPLAY_HEIGHT = 600

# Sizes at or below this edge are treated as off-screen / forge / convert-only
# surfaces, not the game window (classic pattern: set_mode((1, 1), NOFRAME)).
MIN_PLAYABLE_EDGE = 32


@dataclass(frozen=True)
class DisplaySizeDetection:
    """Result of scanning for ``pygame.display.set_mode`` dimensions."""

    width: int
    height: int
    found: bool
    # Relative package path when found (e.g. ``main.py``); None on fallback.
    source: str | None = None


@dataclass(frozen=True)
class _SizeCandidate:
    width: int
    height: int
    relative_path: str
    is_entry: bool
    # True when size is tiny and/or looks like a hidden convert surface.
    is_dummy: bool
    # Lower is better among playable candidates.
    file_rank: int
    # Order of appearance within the file (lower = earlier).
    call_index: int

    @property
    def area(self) -> int:
        return self.width * self.height


def detect_display_size(
    source_dir: Path,
    *,
    entry_module: str,
    package_files: list[str],
) -> DisplaySizeDetection:
    """Best-effort width/height from ``pygame.display.set_mode``.

    Preference order among **playable** sizes (edge >= ``MIN_PLAYABLE_EDGE``):

    1. Calls in the entry module (largest area, then last call wins for ties)
    2. Calls in the same directory as the entry module
    3. Other staged modules (largest area, then path / call order)

    Tiny or NOFRAME-style dummy surfaces never win when a playable size exists.
    If only dummies are found (or nothing), falls back to ``800x600``.
    """
    candidates = _collect_candidates(
        source_dir,
        entry_module=entry_module,
        package_files=package_files,
    )
    chosen = _pick_best_candidate(candidates)
    if chosen is None:
        return DisplaySizeDetection(
            width=DEFAULT_DISPLAY_WIDTH,
            height=DEFAULT_DISPLAY_HEIGHT,
            found=False,
            source=None,
        )
    return DisplaySizeDetection(
        width=chosen.width,
        height=chosen.height,
        found=True,
        source=chosen.relative_path,
    )


def _collect_candidates(
    source_dir: Path,
    *,
    entry_module: str,
    package_files: list[str],
) -> list[_SizeCandidate]:
    entry_relative = f"{entry_module.replace('.', '/')}.py"
    entry_parent = str(PurePosixPath(entry_relative).parent)
    if entry_parent == ".":
        entry_parent = ""

    files = _python_files_for_detection(
        source_dir,
        entry_module=entry_module,
        package_files=package_files,
    )
    candidates: list[_SizeCandidate] = []
    for file_rank, (relative_path, path) in enumerate(files):
        is_entry = relative_path == entry_relative
        parent = str(PurePosixPath(relative_path).parent)
        if parent == ".":
            parent = ""
        same_dir_as_entry = parent == entry_parent
        # Entry first, then same package dir, then everything else (stable file order).
        if is_entry:
            rank = 0
        elif same_dir_as_entry:
            rank = 1
        else:
            rank = 2 + file_rank

        for call_index, size in enumerate(_display_sizes_from_file(path)):
            width, height, is_dummy = size
            candidates.append(
                _SizeCandidate(
                    width=width,
                    height=height,
                    relative_path=relative_path,
                    is_entry=is_entry,
                    is_dummy=is_dummy,
                    file_rank=rank,
                    call_index=call_index,
                )
            )
    return candidates


def _pick_best_candidate(
    candidates: list[_SizeCandidate],
) -> _SizeCandidate | None:
    playable = [c for c in candidates if not c.is_dummy]
    if not playable:
        return None

    # Prefer entry module, then nearby files, then larger area.
    # Within the same file, prefer the *last* playable call (often the real
    # window after a temporary surface) and larger area when mixed.
    def sort_key(c: _SizeCandidate) -> tuple[int, int, int, int]:
        return (
            c.file_rank,
            -c.area,
            -c.call_index if c.is_entry else c.call_index,
            c.call_index,
        )

    return min(playable, key=sort_key)


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


def _display_sizes_from_file(
    path: Path,
) -> list[tuple[int, int, bool]]:
    """Return every resolvable set_mode size in file order: (w, h, is_dummy)."""
    try:
        source = path.read_text(encoding="utf-8")
        module = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, UnicodeError):
        return []

    constants = _module_int_constants(module)
    sizes: list[tuple[int, int, bool]] = []
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        if not _is_set_mode_call(node):
            continue
        parsed = _size_from_set_mode_call(node, constants)
        if parsed is None:
            continue
        width, height = parsed
        is_dummy = _looks_like_dummy_surface(width, height, node)
        sizes.append((width, height, is_dummy))
    return sizes


def _looks_like_dummy_surface(width: int, height: int, node: ast.Call) -> bool:
    if width < MIN_PLAYABLE_EDGE or height < MIN_PLAYABLE_EDGE:
        return True
    # Explicit hidden / off-screen style flags often pair with tiny surfaces;
    # also treat NOFRAME/HIDDEN on very small areas as non-game even if edge
    # is slightly above the floor.
    if _call_has_hidden_display_flag(node) and (width * height) < 10_000:
        return True
    return False


def _call_has_hidden_display_flag(node: ast.Call) -> bool:
    """True when flags look like NOFRAME / HIDDEN / OPENGL-less headless use."""
    flag_nodes: list[ast.AST] = []
    if len(node.args) >= 2:
        flag_nodes.append(node.args[1])
    for keyword in node.keywords:
        if keyword.arg in {"flags", "flag"}:
            flag_nodes.append(keyword.value)

    names: set[str] = set()
    for flag_node in flag_nodes:
        names.update(_flag_names(flag_node))
    # FULLSCREEN / RESIZABLE are normal game flags; only these mark non-game
    # "hidden convert surface" helpers.
    return bool(names & {"NOFRAME", "HIDDEN"})


def _flag_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    if isinstance(node, ast.Attribute):
        names.add(node.attr)
        return names
    if isinstance(node, ast.Name):
        names.add(node.id)
        return names
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.BitOr, ast.BitAnd)):
        names.update(_flag_names(node.left))
        names.update(_flag_names(node.right))
        return names
    if isinstance(node, ast.UnaryOp):
        names.update(_flag_names(node.operand))
        return names
    if isinstance(node, ast.Call):
        # e.g. unlikely wrappers; still walk attributes inside args
        for arg in node.args:
            names.update(_flag_names(arg))
        for keyword in node.keywords:
            names.update(_flag_names(keyword.value))
        return names
    return names


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
        # set_mode(w, h) is not the pygame API, but keep resolving if both ints
        # and no flags-looking second arg that is a Name/Attribute of flags.
        second = node.args[1]
        if isinstance(second, (ast.Name, ast.Attribute, ast.BinOp)):
            # Likely set_mode(size, flags) with size not a tuple — unresolvable.
            return None
        width = _resolve_int(node.args[0], constants)
        height = _resolve_int(second, constants)
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

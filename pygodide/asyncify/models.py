from __future__ import annotations

import ast
from dataclasses import dataclass

from pygodide.asyncify.constants import AsyncifyStatus, DiagnosticStatus


@dataclass(frozen=True)
class AsyncifyResult:
    changed: bool
    status: AsyncifyStatus
    message: str
    relative_path: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class AsyncifyDiagnostic:
    status: DiagnosticStatus
    message: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class TransformTarget:
    function: ast.FunctionDef
    game_loop: ast.While | None = None
    await_calls_to: frozenset[str] = frozenset()


@dataclass(frozen=True)
class EntrypointAnalysis:
    relative_path: str
    module: ast.Module | None = None
    transform_targets: list[TransformTarget] | None = None
    already_async: bool = False
    skip_message: str | None = None
    warnings: tuple[str, ...] = ()

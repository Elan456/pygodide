from __future__ import annotations

import ast

from pygodide.asyncify.ast_utils import dotted_name, iter_game_loops
from pygodide.asyncify.constants import BLOCKING_CALLS, MANUAL_ASYNC_GUIDANCE
from pygodide.asyncify.models import AsyncifyDiagnostic, TransformTarget


def format_smoke_async_warnings(
    diagnostic: AsyncifyDiagnostic,
    *,
    auto_async_enabled: bool,
) -> list[str]:
    warnings: list[str] = []

    if not auto_async_enabled:
        if diagnostic.status == "would-change":
            warnings.append(
                "Smoke warning: auto-async is disabled but the entrypoint looks "
                "like a synchronous Pygame loop. Rebuild with auto-async enabled "
                "or asyncify the entrypoint manually."
            )
        warnings.extend(diagnostic.warnings)
        return warnings

    if diagnostic.status == "would-skip":
        warnings.append(
            "Smoke warning: auto-async cannot safely transform this entrypoint. "
            f"{diagnostic.message} {MANUAL_ASYNC_GUIDANCE}"
        )

    warnings.extend(diagnostic.warnings)
    return warnings


def module_import_warnings(module: ast.Module) -> tuple[str, ...]:
    warnings: list[str] = []
    for statement in module.body:
        if not isinstance(statement, ast.Expr):
            continue
        if not isinstance(statement.value, ast.Call):
            continue
        call_name = dotted_name(statement.value.func)
        if call_name == "asyncio.run":
            warnings.append(
                "Pygodide warning: module-level asyncio.run() executes during "
                "import in the browser and breaks startup. Move it under "
                'if __name__ == "__main__": for local runs only.'
            )
    return tuple(warnings)


def merge_warnings(*warning_groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for warning_group in warning_groups:
        for warning in warning_group:
            if warning not in merged:
                merged.append(warning)
    return tuple(merged)


def blocking_call_warnings(
    module: ast.Module, function: ast.AsyncFunctionDef | ast.FunctionDef
) -> tuple[str, ...]:
    del module  # reserved for future cross-module analysis
    warnings: list[str] = []
    for loop in iter_game_loops(function):
        for node in ast.walk(loop):
            if not isinstance(node, ast.Call):
                continue
            call_name = dotted_name(node.func)
            if call_name in BLOCKING_CALLS:
                warnings.append(
                    "Auto async warning: game loop calls "
                    f"{call_name}(), which can block the browser event loop."
                )
    return tuple(dict.fromkeys(warnings))


def blocking_call_warnings_for_targets(
    module: ast.Module, transform_targets: list[TransformTarget] | None
) -> tuple[str, ...]:
    del module
    if transform_targets is None:
        return ()

    warnings: list[str] = []
    for transform_target in transform_targets:
        if transform_target.game_loop is None:
            continue
        for node in ast.walk(transform_target.game_loop):
            if not isinstance(node, ast.Call):
                continue
            call_name = dotted_name(node.func)
            if call_name in BLOCKING_CALLS:
                warnings.append(
                    "Auto async warning: game loop calls "
                    f"{call_name}(), which can block the browser event loop."
                )
    return tuple(dict.fromkeys(warnings))

from __future__ import annotations

import ast

from pygodide.asyncify.constants import PYGAME_FRAME_SIGNALS


def dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent_name = dotted_name(node.value)
        if parent_name is None:
            return node.attr
        return f"{parent_name}.{node.attr}"
    return None


def is_pygame_frame_signal(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False

    call_name = dotted_name(node.func)
    if call_name in PYGAME_FRAME_SIGNALS:
        return True
    return call_name is not None and call_name.endswith(".tick")


def loop_has_pygame_frame_signal(loop: ast.While) -> bool:
    return any(
        is_pygame_frame_signal(node)
        for statement in loop.body
        for node in ast.walk(statement)
    )


def iter_game_loops(
    function: ast.AsyncFunctionDef | ast.FunctionDef,
) -> list[ast.While]:
    return [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.While) and loop_has_pygame_frame_signal(node)
    ]

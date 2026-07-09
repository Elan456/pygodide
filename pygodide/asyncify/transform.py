from __future__ import annotations

import ast
from pathlib import Path

from pygodide.asyncify.analyze import analyze_entrypoint, entrypoint_relative_path
from pygodide.asyncify.ast_utils import dotted_name
from pygodide.asyncify.models import AsyncifyResult
from pygodide.builder.plan import BuildPlan


def asyncify_entrypoint(build_plan: BuildPlan, output_dir: Path) -> AsyncifyResult:
    relative_path = entrypoint_relative_path(build_plan)
    entrypoint_path = output_dir / relative_path
    analysis = analyze_entrypoint(build_plan, entrypoint_path)

    if analysis.already_async:
        return AsyncifyResult(
            changed=False,
            status="already-async",
            message=analysis.skip_message or "",
            relative_path=relative_path,
            warnings=analysis.warnings,
        )

    if analysis.skip_message is not None or analysis.module is None:
        return AsyncifyResult(
            changed=False,
            status="skipped",
            message=analysis.skip_message or "",
            relative_path=relative_path,
            warnings=analysis.warnings,
        )

    module = analysis.module
    transform_targets = analysis.transform_targets
    assert module is not None
    assert transform_targets is not None

    if not module_imports_asyncio(module):
        module.body.insert(0, ast.Import(names=[ast.alias(name="asyncio")]))

    for transform_target in transform_targets:
        if transform_target.game_loop is not None and not loop_yields_to_asyncio(
            transform_target.game_loop
        ):
            transform_target.game_loop.body.append(asyncio_sleep_statement())
        if transform_target.await_calls_to:
            await_calls_to_functions(
                transform_target.function,
                transform_target.await_calls_to,
            )
        replace_function(module, transform_target.function)

    ast.fix_missing_locations(module)
    transformed_source = ast.unparse(module) + "\n"
    entrypoint_path.write_text(transformed_source, encoding="utf-8")

    return AsyncifyResult(
        changed=True,
        status="changed",
        message=(
            f"Auto async: transformed {relative_path}, inserted await asyncio.sleep(0)"
        ),
        relative_path=relative_path,
        warnings=analysis.warnings,
    )


def module_imports_asyncio(module: ast.Module) -> bool:
    return any(
        isinstance(statement, ast.Import)
        and any(alias.name == "asyncio" for alias in statement.names)
        for statement in module.body
    )


def loop_yields_to_asyncio(loop: ast.While) -> bool:
    return any(
        isinstance(node, ast.Await)
        and isinstance(node.value, ast.Call)
        and dotted_name(node.value.func) == "asyncio.sleep"
        for statement in loop.body
        for node in ast.walk(statement)
    )


def asyncio_sleep_statement() -> ast.Expr:
    return ast.Expr(
        value=ast.Await(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="asyncio", ctx=ast.Load()),
                    attr="sleep",
                    ctx=ast.Load(),
                ),
                args=[ast.Constant(value=0)],
                keywords=[],
            )
        )
    )


def await_calls_to_functions(
    function: ast.FunctionDef, function_names: frozenset[str]
) -> None:
    transformer = AwaitCallsTransformer(function_names)
    function.body = [transformer.visit(statement) for statement in function.body]


class AwaitCallsTransformer(ast.NodeTransformer):
    def __init__(self, function_names: frozenset[str]) -> None:
        self._function_names = function_names

    def visit_Call(self, node: ast.Call) -> ast.AST:
        node = self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id in self._function_names:
            return ast.Await(value=node)
        return node


def replace_function(module: ast.Module, function: ast.FunctionDef) -> None:
    replacement_kwargs = {
        "name": function.name,
        "args": function.args,
        "body": function.body,
        "decorator_list": function.decorator_list,
        "returns": function.returns,
        "type_comment": function.type_comment,
    }
    if hasattr(function, "type_params"):
        replacement_kwargs["type_params"] = function.type_params

    replacement = ast.AsyncFunctionDef(**replacement_kwargs)

    for index, statement in enumerate(module.body):
        if statement is function:
            module.body[index] = replacement
            return

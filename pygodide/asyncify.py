from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pygodide.building import BuildPlan
from pygodide.project_config import load_pygodide_project_config

AsyncifyStatus = Literal["already-async", "changed", "skipped"]
DiagnosticStatus = Literal["already-async", "would-change", "would-skip", "disabled"]
MANUAL_ASYNC_GUIDANCE = (
    "Make the entrypoint async and add await asyncio.sleep(0) once per frame."
)
PYGAME_FRAME_SIGNALS = frozenset(
    {
        "pygame.event.get",
        "pygame.event.pump",
        "pygame.event.wait",
        "pygame.display.update",
        "pygame.display.flip",
    }
)
BLOCKING_CALLS = frozenset(
    {
        "time.sleep",
        "pygame.time.wait",
        "pygame.time.delay",
    }
)


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
class _TransformTarget:
    function: ast.FunctionDef
    game_loop: ast.While | None = None
    await_calls_to: frozenset[str] = frozenset()


@dataclass(frozen=True)
class _EntrypointAnalysis:
    relative_path: str
    module: ast.Module | None = None
    transform_targets: list[_TransformTarget] | None = None
    already_async: bool = False
    skip_message: str | None = None
    warnings: tuple[str, ...] = ()


def resolve_auto_async(
    source_dir: str | Path,
    *,
    cli_auto_async: bool | None = None,
    manifest_auto_async: bool | None = None,
) -> tuple[bool, str]:
    if cli_auto_async is not None:
        return (
            cli_auto_async,
            "CLI --auto-async" if cli_auto_async else "CLI --no-auto-async",
        )

    if manifest_auto_async is not None:
        return manifest_auto_async, "testing_manifest.yaml build.auto-async"

    project_config = load_pygodide_project_config(source_dir)
    if project_config is not None and project_config.auto_async is not None:
        return project_config.auto_async, "[tool.pygodide].auto-async"

    return True, "default"


def diagnose_entrypoint(
    build_plan: BuildPlan, source_dir: str | Path
) -> AsyncifyDiagnostic:
    resolved_source_dir = Path(source_dir).resolve()
    entrypoint_path = resolved_source_dir / _entrypoint_relative_path(build_plan)
    analysis = _analyze_entrypoint(build_plan, entrypoint_path)

    if analysis.already_async:
        return AsyncifyDiagnostic(
            status="already-async",
            message=analysis.skip_message or "",
            warnings=analysis.warnings,
        )

    if analysis.skip_message is not None:
        return AsyncifyDiagnostic(
            status="would-skip",
            message=analysis.skip_message,
            warnings=analysis.warnings,
        )

    return AsyncifyDiagnostic(
        status="would-change",
        message=(
            f"Auto async would transform {analysis.relative_path}, "
            "inserting await asyncio.sleep(0)"
        ),
        warnings=analysis.warnings,
    )


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


def asyncify_entrypoint(build_plan: BuildPlan, output_dir: Path) -> AsyncifyResult:
    relative_path = _entrypoint_relative_path(build_plan)
    entrypoint_path = output_dir / relative_path
    analysis = _analyze_entrypoint(build_plan, entrypoint_path)

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

    if not _module_imports_asyncio(module):
        module.body.insert(0, ast.Import(names=[ast.alias(name="asyncio")]))

    for transform_target in transform_targets:
        if transform_target.game_loop is not None and not _loop_yields_to_asyncio(
            transform_target.game_loop
        ):
            transform_target.game_loop.body.append(_asyncio_sleep_statement())
        if transform_target.await_calls_to:
            _await_calls_to_functions(
                transform_target.function,
                transform_target.await_calls_to,
            )
        _replace_function(module, transform_target.function)

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


def _analyze_entrypoint(
    build_plan: BuildPlan, entrypoint_path: Path
) -> _EntrypointAnalysis:
    relative_path = _entrypoint_relative_path(build_plan)

    if relative_path not in build_plan.staged_files:
        return _EntrypointAnalysis(
            relative_path=relative_path,
            skip_message=(
                f"Auto async: skipped {relative_path}, entrypoint module file "
                f"is not staged. {MANUAL_ASYNC_GUIDANCE}"
            ),
        )

    if not entrypoint_path.is_file():
        return _EntrypointAnalysis(
            relative_path=relative_path,
            skip_message=(
                f"Auto async: skipped {relative_path}, entrypoint module file "
                f"was not found. {MANUAL_ASYNC_GUIDANCE}"
            ),
        )

    source = entrypoint_path.read_text(encoding="utf-8")
    try:
        module = ast.parse(source, filename=str(entrypoint_path))
    except SyntaxError as exc:
        return _EntrypointAnalysis(
            relative_path=relative_path,
            skip_message=(
                f"Auto async: skipped {relative_path}, could not parse Python "
                f"source: {exc}. {MANUAL_ASYNC_GUIDANCE}"
            ),
        )

    import_warnings = _module_import_warnings(module)

    target_function = _find_function_by_name(module, build_plan.entry_function)
    if target_function is None:
        return _EntrypointAnalysis(
            relative_path=relative_path,
            module=module,
            skip_message=(
                f"Auto async: skipped {relative_path}, entrypoint function "
                f"{build_plan.entry_function!r} was not found. {MANUAL_ASYNC_GUIDANCE}"
            ),
            warnings=import_warnings,
        )

    if isinstance(target_function, ast.AsyncFunctionDef):
        warnings = _merge_warnings(
            import_warnings,
            _blocking_call_warnings(module, target_function),
        )
        return _EntrypointAnalysis(
            relative_path=relative_path,
            module=module,
            already_async=True,
            skip_message=(
                "Auto async: already async "
                f"({build_plan.entry_module}:{build_plan.entry_function})"
            ),
            warnings=warnings,
        )

    transform_targets, skip_message = _resolve_transform_targets(
        module,
        target_function,
        relative_path=relative_path,
    )
    warnings = _merge_warnings(
        import_warnings,
        _blocking_call_warnings_for_targets(module, transform_targets),
    )

    if transform_targets is None:
        return _EntrypointAnalysis(
            relative_path=relative_path,
            module=module,
            skip_message=skip_message,
            warnings=warnings,
        )

    return _EntrypointAnalysis(
        relative_path=relative_path,
        module=module,
        transform_targets=transform_targets,
        warnings=warnings,
    )


def _entrypoint_relative_path(build_plan: BuildPlan) -> str:
    return f"{build_plan.entry_module.replace('.', '/')}.py"


def _find_function_by_name(
    module: ast.Module, function_name: str
) -> ast.AsyncFunctionDef | ast.FunctionDef | None:
    for statement in module.body:
        if isinstance(statement, ast.AsyncFunctionDef | ast.FunctionDef):
            if statement.name == function_name:
                return statement
    return None


def _resolve_transform_targets(
    module: ast.Module,
    entrypoint: ast.FunctionDef,
    *,
    relative_path: str,
) -> tuple[list[_TransformTarget] | None, str | None]:
    entrypoint_loop = _find_candidate_game_loop(entrypoint)
    if entrypoint_loop is not None:
        return [_TransformTarget(function=entrypoint, game_loop=entrypoint_loop)], None

    helper_targets = _find_helper_loop_targets(module, entrypoint)
    if len(helper_targets) > 1:
        helper_names = ", ".join(function.name for function, _ in helper_targets)
        return None, (
            f"Auto async: skipped {relative_path}, multiple helper game loops "
            f"found ({helper_names}). {MANUAL_ASYNC_GUIDANCE}"
        )

    if len(helper_targets) == 1:
        helper_function, helper_loop = helper_targets[0]
        return [
            _TransformTarget(
                function=entrypoint,
                await_calls_to=frozenset({helper_function.name}),
            ),
            _TransformTarget(function=helper_function, game_loop=helper_loop),
        ], None

    if _direct_module_function_calls(module, entrypoint):
        return None, (
            f"Auto async: skipped {relative_path}, helper functions were called but "
            f"none contain a recognizable Pygame loop. {MANUAL_ASYNC_GUIDANCE}"
        )

    return None, (
        f"Auto async: skipped {relative_path}, no safe game loop found in the "
        f"entrypoint. {MANUAL_ASYNC_GUIDANCE}"
    )


def _find_helper_loop_targets(
    module: ast.Module, entrypoint: ast.FunctionDef
) -> list[tuple[ast.FunctionDef, ast.While]]:
    called_names = _direct_module_function_calls(module, entrypoint)
    helper_targets: list[tuple[ast.FunctionDef, ast.While]] = []

    for function_name in called_names:
        helper_function = _find_function_by_name(module, function_name)
        if helper_function is None or isinstance(helper_function, ast.AsyncFunctionDef):
            continue

        helper_loop = _find_candidate_game_loop(helper_function)
        if helper_loop is not None:
            helper_targets.append((helper_function, helper_loop))

    return helper_targets


def _module_function_names(module: ast.Module) -> set[str]:
    return {
        statement.name
        for statement in module.body
        if isinstance(statement, ast.AsyncFunctionDef | ast.FunctionDef)
    }


def _direct_module_function_calls(
    module: ast.Module, function: ast.FunctionDef
) -> list[str]:
    defined_names = _module_function_names(module)
    called_names: list[str] = []
    for statement in function.body:
        for node in ast.walk(statement):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in defined_names:
                    called_names.append(node.func.id)
    return called_names


def _find_candidate_game_loop(function: ast.FunctionDef) -> ast.While | None:
    for node in ast.walk(function):
        if isinstance(node, ast.While) and _loop_has_pygame_frame_signal(node):
            return node
    return None


def _loop_has_pygame_frame_signal(loop: ast.While) -> bool:
    return any(
        _is_pygame_frame_signal(node)
        for statement in loop.body
        for node in ast.walk(statement)
    )


def _is_pygame_frame_signal(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False

    call_name = _dotted_name(node.func)
    if call_name in PYGAME_FRAME_SIGNALS:
        return True
    return call_name is not None and call_name.endswith(".tick")


def _module_import_warnings(module: ast.Module) -> tuple[str, ...]:
    warnings: list[str] = []
    for statement in module.body:
        if not isinstance(statement, ast.Expr):
            continue
        if not isinstance(statement.value, ast.Call):
            continue
        call_name = _dotted_name(statement.value.func)
        if call_name == "asyncio.run":
            warnings.append(
                "Pygodide warning: module-level asyncio.run() executes during "
                "import in the browser and breaks startup. Move it under "
                'if __name__ == "__main__": for local runs only.'
            )
    return tuple(warnings)


def _merge_warnings(*warning_groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for warning_group in warning_groups:
        for warning in warning_group:
            if warning not in merged:
                merged.append(warning)
    return tuple(merged)


def _blocking_call_warnings(
    module: ast.Module, function: ast.AsyncFunctionDef | ast.FunctionDef
) -> tuple[str, ...]:
    warnings: list[str] = []
    for loop in _iter_game_loops(function):
        for node in ast.walk(loop):
            if not isinstance(node, ast.Call):
                continue
            call_name = _dotted_name(node.func)
            if call_name in BLOCKING_CALLS:
                warnings.append(
                    "Auto async warning: game loop calls "
                    f"{call_name}(), which can block the browser event loop."
                )
    return tuple(dict.fromkeys(warnings))


def _blocking_call_warnings_for_targets(
    module: ast.Module, transform_targets: list[_TransformTarget] | None
) -> tuple[str, ...]:
    if transform_targets is None:
        return ()

    warnings: list[str] = []
    for transform_target in transform_targets:
        if transform_target.game_loop is None:
            continue
        for node in ast.walk(transform_target.game_loop):
            if not isinstance(node, ast.Call):
                continue
            call_name = _dotted_name(node.func)
            if call_name in BLOCKING_CALLS:
                warnings.append(
                    "Auto async warning: game loop calls "
                    f"{call_name}(), which can block the browser event loop."
                )
    return tuple(dict.fromkeys(warnings))


def _iter_game_loops(
    function: ast.AsyncFunctionDef | ast.FunctionDef,
) -> list[ast.While]:
    return [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.While) and _loop_has_pygame_frame_signal(node)
    ]


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent_name = _dotted_name(node.value)
        if parent_name is None:
            return node.attr
        return f"{parent_name}.{node.attr}"
    return None


def _module_imports_asyncio(module: ast.Module) -> bool:
    return any(
        isinstance(statement, ast.Import)
        and any(alias.name == "asyncio" for alias in statement.names)
        for statement in module.body
    )


def _loop_yields_to_asyncio(loop: ast.While) -> bool:
    return any(
        isinstance(node, ast.Await)
        and isinstance(node.value, ast.Call)
        and _dotted_name(node.value.func) == "asyncio.sleep"
        for statement in loop.body
        for node in ast.walk(statement)
    )


def _asyncio_sleep_statement() -> ast.Expr:
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


def _await_calls_to_functions(
    function: ast.FunctionDef, function_names: frozenset[str]
) -> None:
    transformer = _AwaitCallsTransformer(function_names)
    function.body = [transformer.visit(statement) for statement in function.body]


class _AwaitCallsTransformer(ast.NodeTransformer):
    def __init__(self, function_names: frozenset[str]) -> None:
        self._function_names = function_names

    def visit_Call(self, node: ast.Call) -> ast.AST:
        node = self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id in self._function_names:
            return ast.Await(value=node)
        return node


def _replace_function(module: ast.Module, function: ast.FunctionDef) -> None:
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

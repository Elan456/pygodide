from __future__ import annotations

import ast
from pathlib import Path

from pygodide.asyncify.ast_utils import loop_has_pygame_frame_signal
from pygodide.asyncify.constants import FRAME_YIELD_HINT, MANUAL_ASYNC_GUIDANCE
from pygodide.asyncify.models import (
    AsyncifyDiagnostic,
    EntrypointAnalysis,
    TransformTarget,
)
from pygodide.asyncify.warnings import (
    blocking_call_warnings,
    blocking_call_warnings_for_targets,
    merge_warnings,
    module_import_warnings,
)
from pygodide.builder.plan import BuildPlan


def diagnose_entrypoint(
    build_plan: BuildPlan, source_dir: str | Path
) -> AsyncifyDiagnostic:
    resolved_source_dir = Path(source_dir).resolve()
    entrypoint_path = resolved_source_dir / entrypoint_relative_path(build_plan)
    analysis = analyze_entrypoint(build_plan, entrypoint_path)

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
            f"inserting {FRAME_YIELD_HINT}"
        ),
        warnings=analysis.warnings,
    )


def analyze_entrypoint(
    build_plan: BuildPlan, entrypoint_path: Path
) -> EntrypointAnalysis:
    relative_path = entrypoint_relative_path(build_plan)

    if not entrypoint_path.is_file():
        return EntrypointAnalysis(
            relative_path=relative_path,
            skip_message=(
                f"Auto async: skipped {relative_path}, entrypoint module file "
                f"was not found. {MANUAL_ASYNC_GUIDANCE}"
            ),
        )

    if relative_path not in build_plan.package_files:
        return EntrypointAnalysis(
            relative_path=relative_path,
            skip_message=(
                f"Auto async: skipped {relative_path}, entrypoint module file "
                f"is not included in the build package "
                f"(check [tool.pygodide].include if set). {MANUAL_ASYNC_GUIDANCE}"
            ),
        )

    source = entrypoint_path.read_text(encoding="utf-8")
    try:
        module = ast.parse(source, filename=str(entrypoint_path))
    except SyntaxError as exc:
        return EntrypointAnalysis(
            relative_path=relative_path,
            skip_message=(
                f"Auto async: skipped {relative_path}, could not parse Python "
                f"source: {exc}. {MANUAL_ASYNC_GUIDANCE}"
            ),
        )

    import_warnings = module_import_warnings(module)

    target_function = find_function_by_name(module, build_plan.entry_function)
    if target_function is None:
        return EntrypointAnalysis(
            relative_path=relative_path,
            module=module,
            skip_message=(
                f"Auto async: skipped {relative_path}, entrypoint function "
                f"{build_plan.entry_function!r} was not found. {MANUAL_ASYNC_GUIDANCE}"
            ),
            warnings=import_warnings,
        )

    if isinstance(target_function, ast.AsyncFunctionDef):
        warnings = merge_warnings(
            import_warnings,
            blocking_call_warnings(module, target_function),
        )
        return EntrypointAnalysis(
            relative_path=relative_path,
            module=module,
            already_async=True,
            skip_message=(
                "Auto async: already async "
                f"({build_plan.entry_module}:{build_plan.entry_function})"
            ),
            warnings=warnings,
        )

    transform_targets, skip_message = resolve_transform_targets(
        module,
        target_function,
        relative_path=relative_path,
    )
    warnings = merge_warnings(
        import_warnings,
        blocking_call_warnings_for_targets(module, transform_targets),
    )

    if transform_targets is None:
        return EntrypointAnalysis(
            relative_path=relative_path,
            module=module,
            skip_message=skip_message,
            warnings=warnings,
        )

    return EntrypointAnalysis(
        relative_path=relative_path,
        module=module,
        transform_targets=transform_targets,
        warnings=warnings,
    )


def entrypoint_relative_path(build_plan: BuildPlan) -> str:
    return f"{build_plan.entry_module.replace('.', '/')}.py"


def find_function_by_name(
    module: ast.Module, function_name: str
) -> ast.AsyncFunctionDef | ast.FunctionDef | None:
    for statement in module.body:
        if isinstance(statement, ast.AsyncFunctionDef | ast.FunctionDef):
            if statement.name == function_name:
                return statement
    return None


def resolve_transform_targets(
    module: ast.Module,
    entrypoint: ast.FunctionDef,
    *,
    relative_path: str,
) -> tuple[list[TransformTarget] | None, str | None]:
    entrypoint_loop = find_candidate_game_loop(entrypoint)
    if entrypoint_loop is not None:
        return [TransformTarget(function=entrypoint, game_loop=entrypoint_loop)], None

    helper_targets = find_helper_loop_targets(module, entrypoint)
    if len(helper_targets) > 1:
        helper_names = ", ".join(function.name for function, _ in helper_targets)
        return None, (
            f"Auto async: skipped {relative_path}, multiple helper game loops "
            f"found ({helper_names}). {MANUAL_ASYNC_GUIDANCE}"
        )

    if len(helper_targets) == 1:
        helper_function, helper_loop = helper_targets[0]
        return [
            TransformTarget(
                function=entrypoint,
                await_calls_to=frozenset({helper_function.name}),
            ),
            TransformTarget(function=helper_function, game_loop=helper_loop),
        ], None

    if direct_module_function_calls(module, entrypoint):
        return None, (
            f"Auto async: skipped {relative_path}, helper functions were called but "
            f"none contain a recognizable Pygame loop. {MANUAL_ASYNC_GUIDANCE}"
        )

    return None, (
        f"Auto async: skipped {relative_path}, no safe game loop found in the "
        f"entrypoint. {MANUAL_ASYNC_GUIDANCE}"
    )


def find_helper_loop_targets(
    module: ast.Module, entrypoint: ast.FunctionDef
) -> list[tuple[ast.FunctionDef, ast.While]]:
    called_names = direct_module_function_calls(module, entrypoint)
    helper_targets: list[tuple[ast.FunctionDef, ast.While]] = []

    for function_name in called_names:
        helper_function = find_function_by_name(module, function_name)
        if helper_function is None or isinstance(helper_function, ast.AsyncFunctionDef):
            continue

        helper_loop = find_candidate_game_loop(helper_function)
        if helper_loop is not None:
            helper_targets.append((helper_function, helper_loop))

    return helper_targets


def module_function_names(module: ast.Module) -> set[str]:
    return {
        statement.name
        for statement in module.body
        if isinstance(statement, ast.AsyncFunctionDef | ast.FunctionDef)
    }


def direct_module_function_calls(
    module: ast.Module, function: ast.FunctionDef
) -> list[str]:
    defined_names = module_function_names(module)
    called_names: list[str] = []
    for statement in function.body:
        for node in ast.walk(statement):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in defined_names:
                    called_names.append(node.func.id)
    return called_names


def find_candidate_game_loop(function: ast.FunctionDef) -> ast.While | None:
    for node in ast.walk(function):
        if isinstance(node, ast.While) and loop_has_pygame_frame_signal(node):
            return node
    return None

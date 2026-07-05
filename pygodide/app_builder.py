from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pygodide.asyncify import AsyncifyResult, asyncify_entrypoint
from pygodide.build_logging import log_build_choices
from pygodide.building import build_plan_for_source, copy_staged_files
from pygodide.dep_handling.pyodide_resolution import (
    build_install_plan,
    collect_requirements,
)
from pygodide.rendering import render_boot_js, render_index_html


def build_app(
    source_dir: Path,
    *,
    app_spec: str | None = None,
    deps: list[str] | None = None,
    auto_async: bool = True,
    log: Callable[[str], None] | None = print,
) -> Path:
    build_plan = build_plan_for_source(source_dir, app_spec=app_spec)
    dependency_collection = collect_requirements(
        source_dir,
        extra_dependencies=deps,
    )
    install_plan = build_install_plan(dependency_collection.packages)

    if log is not None:
        log_build_choices(
            build_plan=build_plan,
            dependency_collection=dependency_collection,
            install_plan=install_plan,
            log=log,
        )

    output_dir = build_plan.output_dir
    copy_staged_files(
        source_dir=build_plan.source_dir,
        output_dir=output_dir,
        staged_files=build_plan.staged_files,
    )
    if auto_async:
        asyncify_result = asyncify_entrypoint(build_plan, output_dir)
        if log is not None:
            _log_asyncify_result(asyncify_result, output_dir, log)
    elif log is not None:
        log("Auto async: disabled")

    boot_script_name = "boot.js"
    index_html = render_index_html(
        title=build_plan.title,
        canvas_width=build_plan.canvas_width,
        canvas_height=build_plan.canvas_height,
        boot_script_path=f"./{boot_script_name}",
    )

    index_output_path = output_dir / "index.html"
    index_output_path.write_text(index_html, encoding="utf-8")

    boot_js = render_boot_js(
        staged_files=build_plan.staged_files,
        pyodide_packages=install_plan.pyodide_packages,
        micropip_packages=install_plan.micropip_packages,
        declared_package_names=[pkg.name for pkg in dependency_collection.packages],
        python_path_entries=build_plan.python_path_entries,
        entry_module=build_plan.entry_module,
        entry_function=build_plan.entry_function,
    )

    boot_output_path = output_dir / boot_script_name
    boot_output_path.parent.mkdir(parents=True, exist_ok=True)
    boot_output_path.write_text(boot_js, encoding="utf-8")

    return output_dir


def _log_asyncify_result(
    result: AsyncifyResult,
    output_dir: Path,
    log: Callable[[str], None],
) -> None:
    log(result.message)
    for warning in result.warnings:
        log(warning)
    if not result.changed or result.relative_path is None:
        return

    transformed_path = output_dir / result.relative_path
    log(f"Auto async transformed source ({result.relative_path}):")
    log(transformed_path.read_text(encoding="utf-8").rstrip())

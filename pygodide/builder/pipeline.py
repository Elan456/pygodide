from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pygodide.asyncify import (
    AsyncifyResult,
    asyncify_entrypoint,
    diagnose_entrypoint,
)
from pygodide.asyncify.constants import MANUAL_ASYNC_GUIDANCE
from pygodide.builder.plan import (
    BuildPlan,
    build_plan_for_source,
    copy_package_files,
)
from pygodide.dep_handling.pyodide_resolution import (
    build_install_plan,
    collect_requirements,
)
from pygodide.logs import log_build_choices
from pygodide.rendering import (
    content_cache_buster,
    ensure_favicon,
    package_files_cache_buster,
    render_boot_js,
    render_index_html,
    resolve_favicon,
    write_logo,
)


def build_app(
    source_dir: Path,
    *,
    app_spec: str | None = None,
    deps: list[str] | None = None,
    auto_async: bool = True,
    canvas_width: int | None = None,
    canvas_height: int | None = None,
    canvas_fit: bool | None = None,
    canvas_fill: bool | None = None,
    log: Callable[[str], None] | None = print,
) -> Path:
    build_plan = build_plan_for_source(
        source_dir,
        app_spec=app_spec,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        canvas_fit=canvas_fit,
        canvas_fill=canvas_fill,
    )
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
    copy_package_files(
        source_dir=build_plan.source_dir,
        output_dir=output_dir,
        package_files=build_plan.package_files,
    )
    if auto_async:
        asyncify_result = asyncify_entrypoint(build_plan, output_dir)
        if log is not None:
            _log_asyncify_result(asyncify_result, output_dir, log)
    else:
        if log is not None:
            log("Auto async: disabled")
            _log_disabled_auto_async_risk(build_plan, output_dir, log)

    boot_script_name = "boot.js"
    logo_name = "pygodide-logo.svg"
    favicon = resolve_favicon(build_plan.source_dir)
    if log is not None:
        log(f"Favicon: {favicon.source_label}")
    ensure_favicon(output_dir, favicon)
    write_logo(output_dir, filename=logo_name)

    # Hash after copy/asyncify so transformed entry sources are included.
    asset_cache_buster = package_files_cache_buster(
        output_dir, build_plan.package_files
    )
    boot_js = render_boot_js(
        package_files=build_plan.package_files,
        pyodide_packages=install_plan.pyodide_packages,
        micropip_packages=install_plan.micropip_packages,
        declared_package_names=[pkg.name for pkg in dependency_collection.packages],
        python_path_entries=build_plan.python_path_entries,
        entry_module=build_plan.entry_module,
        entry_function=build_plan.entry_function,
        canvas_layout=build_plan.canvas_layout,
        canvas_width=build_plan.canvas_width,
        canvas_height=build_plan.canvas_height,
        asset_cache_buster=asset_cache_buster,
    )

    boot_output_path = output_dir / boot_script_name
    boot_output_path.parent.mkdir(parents=True, exist_ok=True)
    boot_output_path.write_text(boot_js, encoding="utf-8")

    # Bust HTTP caches when boot.js changes (Firefox keeps module scripts even
    # when the Storage panel is empty).
    index_html = render_index_html(
        title=build_plan.title,
        canvas_width=build_plan.canvas_width,
        canvas_height=build_plan.canvas_height,
        canvas_layout=build_plan.canvas_layout,
        boot_script_path=f"./{boot_script_name}",
        favicon_path=f"./{favicon.filename}",
        favicon_type=favicon.media_type,
        logo_path=f"./{logo_name}",
        boot_cache_buster=content_cache_buster(boot_js),
    )

    index_output_path = output_dir / "index.html"
    index_output_path.write_text(index_html, encoding="utf-8")

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


def _log_disabled_auto_async_risk(
    build_plan: BuildPlan,
    source_dir: Path,
    log: Callable[[str], None],
) -> None:
    """Warn at build time when --no-auto-async meets a sync game loop."""
    del source_dir  # plan carries source_dir
    diagnostic = diagnose_entrypoint(build_plan, build_plan.source_dir)
    if diagnostic.status != "would-change":
        return
    log(
        "Warning: auto-async is disabled but the entrypoint looks like a "
        "synchronous Pygame game loop. In the browser that usually freezes with "
        "hang help on the page. Rebuild without --no-auto-async, or manually: "
        f"{MANUAL_ASYNC_GUIDANCE}"
    )

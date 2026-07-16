from __future__ import annotations

from pathlib import Path

import typer

from pygodide.asyncify import resolve_auto_async
from pygodide.builder import build_app
from pygodide.builder.plan import (
    build_output_dir,
    clean_build_dir,
    warn_if_pygodide_output_dir,
)
from pygodide.builder.zip import create_itch_zip, default_itch_zip_path
from pygodide.logs import (
    build_log_tee,
    initialize_build_log,
    write_build_log_failure,
    write_build_log_success,
)
from pygodide.rendering import DEFAULT_READY_LOG
from pygodide.serving import serve_directory_forever

DEFAULT_SERVE_PORT = 8000
DEFAULT_SMOKE_PATH = "/"
DEFAULT_SMOKE_TIMEOUT_MS = 120_000
DEFAULT_SMOKE_POST_READY_MS = 500


def run_build_command(
    path: Path,
    *,
    serve: bool,
    app_spec: str | None,
    deps: list[str] | None,
    auto_async: bool | None = None,
    clean: bool = False,
    create_zip: bool = False,
    zip_output: Path | None = None,
    canvas_width: int | None = None,
    canvas_height: int | None = None,
    canvas_fit: bool | None = None,
    canvas_fill: bool | None = None,
    port: int | None = None,
) -> None:
    if port is not None and not serve:
        raise typer.BadParameter("--port requires --serve")

    source_dir = path.resolve()
    warn_if_pygodide_output_dir(
        source_dir,
        log=lambda message: typer.secho(message, fg=typer.colors.YELLOW, err=True),
    )

    if clean or create_zip:
        clean_build_dir(source_dir)

    resolved_auto_async, auto_async_source = resolve_auto_async(
        source_dir,
        cli_auto_async=auto_async,
    )
    build_log_path = initialize_build_log(
        source_dir,
        app_spec=app_spec,
        deps=deps,
        serve=serve,
        auto_async=resolved_auto_async,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )
    typer.echo(f"Build log: {build_log_path}")
    if auto_async_source != "default":
        typer.echo(f"Auto-async setting: {resolved_auto_async} ({auto_async_source})")

    try:
        output_dir = build_app(
            source_dir,
            app_spec=app_spec,
            deps=deps,
            auto_async=resolved_auto_async,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            canvas_fit=canvas_fit,
            canvas_fill=canvas_fill,
            log=build_log_tee(build_log_path, typer.echo),
        )
    except ValueError as exc:
        write_build_log_failure(build_log_path, exc)
        raise typer.BadParameter(str(exc)) from exc
    except Exception as exc:
        write_build_log_failure(build_log_path, exc)
        raise

    write_build_log_success(build_log_path)

    if create_zip:
        resolved_zip_path = create_itch_zip(
            output_dir,
            zip_output or default_itch_zip_path(source_dir),
        )
        typer.echo(f"Created itch.io ZIP: {resolved_zip_path}")

    if serve:
        _serve_or_raise(
            output_dir,
            port=port if port is not None else DEFAULT_SERVE_PORT,
        )


def run_serve_command(path: Path, *, port: int = DEFAULT_SERVE_PORT) -> None:
    output_dir = build_output_dir(path)
    if not output_dir.is_dir():
        raise typer.BadParameter(
            f"{output_dir} does not exist. Please run 'pygodide build' first."
        )

    _serve_or_raise(output_dir, port=port)


def run_smoke_command(
    path: Path,
    *,
    suite: bool,
    targets: list[str] | None,
    app_spec: str | None,
    deps: list[str] | None,
    smoke_path: str,
    timeout_ms: int,
    post_ready_ms: int,
    ready_log: str,
    build_only: bool,
    auto_async: bool | None = None,
    canvas_width: int | None = None,
    canvas_height: int | None = None,
    canvas_fit: bool | None = None,
    canvas_fill: bool | None = None,
    verbose: bool = False,
) -> None:
    from pygodide.smoke import (
        SmokeConfig,
        resolve_smoke_config,
        run_smoke_suite,
        smoke_test_app,
    )

    if suite:
        _reject_suite_incompatible_flags(
            app_spec=app_spec,
            deps=deps,
            smoke_path=smoke_path,
            timeout_ms=timeout_ms,
            post_ready_ms=post_ready_ms,
            ready_log=ready_log,
            auto_async=auto_async,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            canvas_fit=canvas_fit,
            canvas_fill=canvas_fill,
        )
        results = run_smoke_suite(
            path,
            target_names=targets,
            build_only=build_only,
            echo=typer.echo,
            verbose=verbose,
        )
        failures = [result for result in results if not result.success]

        if failures:
            raise typer.Exit(1)
        return

    if targets:
        raise typer.BadParameter("--target can only be used with --suite")
    if not smoke_path.startswith("/"):
        raise typer.BadParameter("--smoke-path must start with '/'")
    if timeout_ms <= 0:
        raise typer.BadParameter("--timeout-ms must be a positive integer")
    if post_ready_ms < 0:
        raise typer.BadParameter("--post-ready-ms must be a non-negative integer")

    try:
        smoke_test_app(
            path,
            app_spec=app_spec,
            deps=deps,
            auto_async=auto_async,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            canvas_fit=canvas_fit,
            canvas_fill=canvas_fill,
            smoke=resolve_smoke_config(
                path,
                smoke=SmokeConfig(
                    path=smoke_path,
                    ready_log=ready_log,
                    timeout_ms=timeout_ms,
                    post_ready_ms=post_ready_ms,
                ),
            ),
            build_only=build_only,
            echo=typer.echo if verbose else None,
            verbose=verbose,
        )
        if not verbose and not build_only:
            typer.echo("Smoke test passed")
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _serve_or_raise(output_dir: Path, *, port: int) -> None:
    try:
        serve_directory_forever(output_dir, port=port)
    except RuntimeError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _reject_suite_incompatible_flags(
    *,
    app_spec: str | None,
    deps: list[str] | None,
    smoke_path: str,
    timeout_ms: int,
    post_ready_ms: int,
    ready_log: str,
    auto_async: bool | None,
    canvas_width: int | None,
    canvas_height: int | None,
    canvas_fit: bool | None,
    canvas_fill: bool | None,
) -> None:
    """Fail when single-app smoke flags are mixed with --suite.

    Suite runs use each target's testing_manifest.yaml; per-app CLI overrides
    would be ambiguous, so they are rejected rather than silently ignored.
    """
    incompatible: list[str] = []
    if app_spec is not None:
        incompatible.append("--app")
    if deps:
        incompatible.append("--dep")
    if auto_async is not None:
        incompatible.append("--auto-async/--no-auto-async")
    if canvas_width is not None:
        incompatible.append("--canvas-width")
    if canvas_height is not None:
        incompatible.append("--canvas-height")
    if canvas_fit is not None:
        incompatible.append("--canvas-fit/--no-canvas-fit")
    if canvas_fill is not None:
        incompatible.append("--canvas-fill/--no-canvas-fill")
    if smoke_path != DEFAULT_SMOKE_PATH:
        incompatible.append("--smoke-path")
    if timeout_ms != DEFAULT_SMOKE_TIMEOUT_MS:
        incompatible.append("--timeout-ms")
    if post_ready_ms != DEFAULT_SMOKE_POST_READY_MS:
        incompatible.append("--post-ready-ms")
    if ready_log != DEFAULT_READY_LOG:
        incompatible.append("--ready-log")

    if incompatible:
        flags = ", ".join(incompatible)
        raise typer.BadParameter(
            f"Cannot combine --suite with single-app options: {flags}. "
            "Configure each target via testing_manifest.yaml instead."
        )

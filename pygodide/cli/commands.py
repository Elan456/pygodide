from __future__ import annotations

from pathlib import Path

import typer

from pygodide.app_builder import build_app
from pygodide.asyncify import resolve_auto_async
from pygodide.build_logging import (
    build_log_tee,
    initialize_build_log,
    write_build_log_failure,
    write_build_log_success,
)
from pygodide.building import build_output_dir, clean_build_dir
from pygodide.packaging import create_itch_zip, default_itch_zip_path
from pygodide.serving import serve_directory_forever


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
) -> None:
    source_dir = path.resolve()
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
        serve_directory_forever(output_dir)


def run_serve_command(path: Path, *, port: int = 8000) -> None:
    output_dir = build_output_dir(path)
    if not output_dir.is_dir():
        raise RuntimeError(f"{output_dir} does not exist. Please run 'build' first.")

    serve_directory_forever(output_dir, port=port)


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
    verbose: bool = False,
) -> None:
    from pygodide.compatibility import (
        SmokeConfig,
        resolve_smoke_config,
        run_compatibility_suite,
        smoke_test_app,
    )

    if suite:
        results = run_compatibility_suite(
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

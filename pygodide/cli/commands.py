from __future__ import annotations

from pathlib import Path

import typer

from pygodide.app_builder import build_app
from pygodide.build_logging import (
    build_log_tee,
    initialize_build_log,
    write_build_log_failure,
    write_build_log_success,
)
from pygodide.building import build_output_dir
from pygodide.serving import serve_directory_forever


def run_build_command(
    path: Path,
    *,
    serve: bool,
    app_spec: str | None,
    deps: list[str] | None,
) -> None:
    source_dir = path.resolve()
    build_log_path = initialize_build_log(
        source_dir,
        app_spec=app_spec,
        deps=deps,
        serve=serve,
    )
    typer.echo(f"Build log: {build_log_path}")

    try:
        output_dir = build_app(
            source_dir,
            app_spec=app_spec,
            deps=deps,
            log=build_log_tee(build_log_path, typer.echo),
        )
    except ValueError as exc:
        write_build_log_failure(build_log_path, exc)
        raise typer.BadParameter(str(exc)) from exc
    except Exception as exc:
        write_build_log_failure(build_log_path, exc)
        raise

    write_build_log_success(build_log_path)

    if serve:
        serve_directory_forever(output_dir)


def run_serve_command(path: Path) -> None:
    output_dir = build_output_dir(path)
    if not output_dir.is_dir():
        raise RuntimeError(f"{output_dir} does not exist. Please run 'build' first.")

    serve_directory_forever(output_dir)


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
) -> None:
    from pygodide.compatibility import (
        SmokeConfig,
        run_compatibility_suite,
        smoke_test_app,
    )

    if suite:
        results = run_compatibility_suite(
            path,
            target_names=targets,
            build_only=build_only,
            echo=typer.echo,
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
            smoke=SmokeConfig(
                path=smoke_path,
                ready_log=ready_log,
                timeout_ms=timeout_ms,
                post_ready_ms=post_ready_ms,
            ),
            build_only=build_only,
            echo=typer.echo,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

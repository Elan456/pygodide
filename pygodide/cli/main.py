from pathlib import Path
from typing import Annotated

import typer

from pygodide.cli.commands import (
    run_build_command,
    run_serve_command,
    run_smoke_command,
)
from pygodide.rendering import DEFAULT_READY_LOG

app = typer.Typer(
    name="Pygodide CLI",
    help="Bundle your pygame app and run it in the browser with Pyodide.",
)


@app.command()
def build(
    path: Annotated[
        Path,
        typer.Argument(help="Root directory of the Pygame app to build"),
    ],
    serve: bool = typer.Option(
        False,
        help="Whether to serve the built app after building",
    ),
    app_spec: Annotated[
        str | None,
        typer.Option(
            "--app",
            help="Entrypoint in 'module:callable' format. Overrides "
            "[tool.pygodide].app when provided.",
        ),
    ] = None,
    deps: Annotated[
        list[str] | None,
        typer.Option(
            "--dep",
            help="Additional dependency requirement to include. Repeat for "
            "multiple dependencies.",
        ),
    ] = None,
):
    """
    Bundle a Pygame app and generate the HTML and JS files needed to run it in the
    browser with Pyodide.
    """
    run_build_command(
        path,
        serve=serve,
        app_spec=app_spec,
        deps=deps,
    )


@app.command()
def serve(
    path: Annotated[
        Path,
        typer.Argument(help="Source directory or build directory to serve"),
    ],
):
    """
    Serve the built Pygodide app from the build directory.
    """
    run_serve_command(path)


@app.command("smoke")
def smoke(
    path: Annotated[
        Path,
        typer.Argument(help="Source app directory to build and smoke test."),
    ],
    suite: Annotated[
        bool,
        typer.Option(
            "--suite",
            help=(
                "Treat PATH as a directory of testing_manifest.yaml target "
                "fixtures and run all targets by default."
            ),
        ),
    ] = False,
    targets: Annotated[
        list[str] | None,
        typer.Option(
            "--target",
            "-t",
            help=(
                "Only with --suite: filter the suite to a manifest name. "
                "Repeat to include multiple targets."
            ),
        ),
    ] = None,
    app_spec: Annotated[
        str | None,
        typer.Option(
            "--app",
            help="Entrypoint in 'module:callable' format. Overrides "
            "[tool.pygodide].app when provided.",
        ),
    ] = None,
    deps: Annotated[
        list[str] | None,
        typer.Option(
            "--dep",
            help="Additional dependency requirement to include. Repeat for "
            "multiple dependencies.",
        ),
    ] = None,
    smoke_path: Annotated[
        str,
        typer.Option(
            "--smoke-path",
            help="URL path to load from the built app during the smoke test.",
        ),
    ] = "/",
    timeout_ms: Annotated[
        int,
        typer.Option(
            "--timeout-ms",
            help="Milliseconds to wait for the generated app ready log.",
        ),
    ] = 120_000,
    post_ready_ms: Annotated[
        int,
        typer.Option(
            "--post-ready-ms",
            help="Milliseconds to keep listening for errors after the ready log.",
        ),
    ] = 500,
    ready_log: Annotated[
        str,
        typer.Option(
            "--ready-log",
            help="Console log message that marks the generated app as ready.",
        ),
    ] = DEFAULT_READY_LOG,
    build_only: Annotated[
        bool,
        typer.Option(
            "--build-only",
            help="Build without launching Playwright.",
        ),
    ] = False,
):
    """
    Build and smoke-test an app in a headless browser.
    """
    run_smoke_command(
        path,
        suite=suite,
        targets=targets,
        app_spec=app_spec,
        deps=deps,
        smoke_path=smoke_path,
        timeout_ms=timeout_ms,
        post_ready_ms=post_ready_ms,
        ready_log=ready_log,
        build_only=build_only,
    )


@app.command()
def hello(name: str):
    """
    Print a greeting message to the specified name.
    """
    print(f"Hello, {name}!")


if __name__ == "__main__":
    app()

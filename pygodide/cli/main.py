from pathlib import Path
from typing import Annotated

import typer

from pygodide import __version__
from pygodide.cli.runners import (
    run_build_command,
    run_serve_command,
    run_smoke_command,
)
from pygodide.rendering import DEFAULT_READY_LOG

app = typer.Typer(
    name="Pygodide CLI",
    help="Bundle your pygame app and run it in the browser with Pyodide.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"pygodide {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show the version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Bundle your pygame app and run it in the browser with Pyodide."""


@app.command(short_help="Package a Pygame app to run in the browser.")
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
    auto_async: Annotated[
        bool | None,
        typer.Option(
            "--auto-async/--no-auto-async",
            help=(
                "Automatically adapt simple synchronous Pygame loops to yield "
                "to the browser event loop. Overrides [tool.pygodide].auto-async "
                "when provided."
            ),
        ),
    ] = None,
    clean: Annotated[
        bool,
        typer.Option(
            "--clean",
            help="Remove the build directory before building.",
        ),
    ] = False,
    create_zip: Annotated[
        bool,
        typer.Option(
            "--zip",
            help=(
                "Create an itch.io-ready ZIP of the build output. "
                "Defaults to PROJECT_DIR/PROJECT_NAME.zip. "
                "Implies --clean."
            ),
        ),
    ] = False,
    zip_output: Annotated[
        Path | None,
        typer.Option(
            "--zip-output",
            help="Path for the itch.io ZIP. Only used with --zip.",
        ),
    ] = None,
    canvas_width: Annotated[
        int | None,
        typer.Option(
            "--canvas-width",
            min=1,
            help=(
                "Canvas width in pixels (with --canvas-height). Alone: fixed "
                "box. With --canvas-fit: aspect ratio to scale into the "
                "viewport (useful when set_mode is not auto-discovered). "
                "Does not change set_mode. Overrides "
                "[tool.pygodide].canvas-width."
            ),
        ),
    ] = None,
    canvas_height: Annotated[
        int | None,
        typer.Option(
            "--canvas-height",
            min=1,
            help=(
                "Canvas height in pixels (with --canvas-width). Alone: fixed "
                "box. With --canvas-fit: aspect ratio for viewport scaling. "
                "Does not change set_mode. Overrides "
                "[tool.pygodide].canvas-height."
            ),
        ),
    ] = None,
    canvas_fit: Annotated[
        bool | None,
        typer.Option(
            "--canvas-fit/--no-canvas-fit",
            help=(
                "Scale to the largest viewport size that keeps aspect ratio. "
                "Aspect comes from --canvas-width/--canvas-height when set, "
                "else auto-discovered set_mode size. Overrides "
                "[tool.pygodide].canvas-fit. Cannot combine with --canvas-fill."
            ),
        ),
    ] = None,
    canvas_fill: Annotated[
        bool | None,
        typer.Option(
            "--canvas-fill/--no-canvas-fill",
            help=(
                "Stretch the canvas to fill the browser viewport (may change "
                "aspect ratio). Overrides [tool.pygodide].canvas-fill. Cannot "
                "combine with --canvas-fit."
            ),
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
        auto_async=auto_async,
        clean=clean,
        create_zip=create_zip,
        zip_output=zip_output,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        canvas_fit=canvas_fit,
        canvas_fill=canvas_fill,
    )


@app.command(short_help="Serve a built app locally over HTTP.")
def serve(
    path: Annotated[
        Path,
        typer.Argument(help="Source directory or build directory to serve"),
    ],
    port: Annotated[
        int,
        typer.Option(
            "--port",
            "-p",
            min=1,
            max=65535,
            help="Port to listen on.",
        ),
    ] = 8000,
):
    """
    Serve the built Pygodide app from the build directory.
    """
    run_serve_command(path, port=port)


@app.command("smoke", short_help="Build and verify an app in a headless browser.")
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
            help="Milliseconds to wait for the ready log and loading status to clear.",
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
    auto_async: Annotated[
        bool | None,
        typer.Option(
            "--auto-async/--no-auto-async",
            help=(
                "Automatically adapt simple synchronous Pygame loops before "
                "smoke testing. Overrides [tool.pygodide].auto-async when provided."
            ),
        ),
    ] = None,
    canvas_width: Annotated[
        int | None,
        typer.Option(
            "--canvas-width",
            min=1,
            help=(
                "Canvas width in pixels (with --canvas-height). Alone: fixed "
                "box. With --canvas-fit: aspect ratio for viewport scaling. "
                "Overrides [tool.pygodide].canvas-width."
            ),
        ),
    ] = None,
    canvas_height: Annotated[
        int | None,
        typer.Option(
            "--canvas-height",
            min=1,
            help=(
                "Canvas height in pixels (with --canvas-width). Alone: fixed "
                "box. With --canvas-fit: aspect ratio for viewport scaling. "
                "Overrides [tool.pygodide].canvas-height."
            ),
        ),
    ] = None,
    canvas_fit: Annotated[
        bool | None,
        typer.Option(
            "--canvas-fit/--no-canvas-fit",
            help=(
                "Scale to the largest viewport size that keeps aspect ratio. "
                "Use with --canvas-width/--canvas-height when set_mode is not "
                "discovered. Overrides [tool.pygodide].canvas-fit."
            ),
        ),
    ] = None,
    canvas_fill: Annotated[
        bool | None,
        typer.Option(
            "--canvas-fill/--no-canvas-fill",
            help=(
                "Stretch the canvas to fill the browser viewport (may change "
                "aspect ratio). Overrides [tool.pygodide].canvas-fill."
            ),
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Print build and smoke details to the console.",
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
        auto_async=auto_async,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        canvas_fit=canvas_fit,
        canvas_fill=canvas_fill,
        verbose=verbose,
    )


if __name__ == "__main__":
    app()

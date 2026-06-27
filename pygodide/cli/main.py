import http.server
import socketserver
from collections.abc import Callable
from errno import EADDRINUSE
from functools import partial
from pathlib import Path
from typing import Annotated

import typer
from jinja2 import Environment, PackageLoader, select_autoescape

from pygodide.building import (
    build_output_dir,
    build_plan_for_source,
    copy_staged_files,
)
from pygodide.dep_handling.pyodide_resolution import (
    build_install_plan,
    collect_requirements,
)

app = typer.Typer(name="Pygodide CLI", help="A command-line interface for Pygodide.")

DEFAULT_PYODIDE_PACKAGES = ["pygame-ce"]
DEFAULT_PYTHON_PATH_ENTRIES = ["/"]
DEFAULT_STAGED_FILES = ["main.py"]
DEFAULT_READY_LOG = "[pygodide] ready"


def _template_environment() -> Environment:
    return Environment(
        loader=PackageLoader("pygodide", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )


def render_index_html(
    *,
    title: str = "Pygame Pyodide Test",
    lang: str = "en",
    status_text: str = "Loading...",
    status_element_id: str = "status",
    canvas_element_id: str = "canvas",
    canvas_width: int = 800,
    canvas_height: int = 600,
    pyodide_url: str = "https://cdn.jsdelivr.net/pyodide/v314.0.0/full/pyodide.js",
    boot_script_path: str = "./boot.js",
) -> str:
    template = _template_environment().get_template("index.html")
    return template.render(
        title=title,
        lang=lang,
        status_text=status_text,
        status_element_id=status_element_id,
        canvas_element_id=canvas_element_id,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        pyodide_url=pyodide_url,
        boot_script_path=boot_script_path,
    )


def _build_startup_python_code(
    *, entry_module: str, entry_function: str, python_path_entries: list[str]
) -> str:
    lines = [
        "import inspect",
        "import sys",
    ]

    for entry in python_path_entries:
        lines.append(f"if {entry!r} not in sys.path:")
        lines.append(f"    sys.path.append({entry!r})")

    lines.extend(
        [
            f"from {entry_module} import {entry_function}",
            f"_pygodide_entrypoint = {entry_function}()",
            "if inspect.isawaitable(_pygodide_entrypoint):",
            "    await _pygodide_entrypoint",
        ]
    )
    return "\n".join(lines)


def render_boot_js(
    *,
    status_element_id: str = "status",
    canvas_element_id: str = "canvas",
    pyodide_packages: list[str] | None = None,
    micropip_packages: list[str] | None = None,
    declared_package_names: list[str] | None = None,
    staged_files: list[str] | None = None,
    python_files: list[str] | None = None,
    python_path_entries: list[str] | None = None,
    asset_base_path: str = "./",
    virtual_fs_root: str = "/",
    entry_module: str = "main",
    entry_function: str = "main",
    startup_python_code: str | None = None,
    starting_pyodide_status_text: str = "Starting Pyodide...",
    loading_packages_status_text: str = "Loading Python packages...",
    staging_files_status_text: str = "Staging app files...",
    loading_app_status_text: str = "Loading Python app...",
    loading_app_hint_text: str = (
        "If the page stays here, your app is probably blocking the browser "
        "event loop. For Pyodide game loops, make the entrypoint async and "
        "add await asyncio.sleep(0)."
    ),
    running_status_text: str = "Running",
    ready_log: str = DEFAULT_READY_LOG,
) -> str:
    template = _template_environment().get_template("boot.js")
    if python_path_entries is None:
        resolved_python_path_entries = DEFAULT_PYTHON_PATH_ENTRIES
    else:
        resolved_python_path_entries = python_path_entries
    resolved_staged_files = (
        staged_files
        if staged_files is not None
        else python_files
        if python_files is not None
        else DEFAULT_STAGED_FILES
    )
    resolved_startup_python_code = startup_python_code or _build_startup_python_code(
        entry_module=entry_module,
        entry_function=entry_function,
        python_path_entries=resolved_python_path_entries,
    )

    return template.render(
        status_element_id=status_element_id,
        canvas_element_id=canvas_element_id,
        pyodide_packages=(
            pyodide_packages
            if pyodide_packages is not None
            else DEFAULT_PYODIDE_PACKAGES
        ),
        micropip_packages=micropip_packages if micropip_packages is not None else [],
        declared_package_names=(
            declared_package_names if declared_package_names is not None else []
        ),
        staged_files=resolved_staged_files,
        asset_base_path=asset_base_path,
        virtual_fs_root=virtual_fs_root,
        startup_python_code=resolved_startup_python_code,
        starting_pyodide_status_text=starting_pyodide_status_text,
        loading_packages_status_text=loading_packages_status_text,
        staging_files_status_text=staging_files_status_text,
        loading_app_status_text=loading_app_status_text,
        loading_app_hint_text=loading_app_hint_text,
        running_status_text=running_status_text,
        ready_log=ready_log,
    )


def build_app(
    source_dir: Path,
    *,
    app_spec: str | None = None,
    deps: list[str] | None = None,
    log: Callable[[str], None] | None = typer.echo,
) -> Path:
    build_plan = build_plan_for_source(source_dir, app_spec=app_spec)
    dependency_collection = collect_requirements(
        source_dir,
        extra_dependencies=deps,
    )
    install_plan = build_install_plan(dependency_collection.packages)

    if log is not None:
        _log_build_choices(
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
    source_dir = path.resolve()
    try:
        output_dir = build_app(source_dir, app_spec=app_spec, deps=deps)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if serve:
        _serve(output_dir)


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

    output_dir = build_output_dir(path)
    if not output_dir.is_dir():
        raise RuntimeError(f"{output_dir} does not exist. Please run 'build' first.")

    _serve(output_dir)


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


class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def _serve(directory: Path, port: int = 8000):
    handler = partial(NoCacheHTTPRequestHandler, directory=str(directory))

    try:
        with ReusableTCPServer(("", port), handler) as httpd:
            print(f"Serving {directory} at http://localhost:{port}")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("Shutting down server...")
    except OSError as exc:
        if exc.errno == EADDRINUSE:
            raise RuntimeError(
                f"Port {port} is already in use. Stop the other server or choose a "
                "different port."
            ) from exc
        raise

    print("Server stopped.")


@app.command()
def hello(name: str):
    """
    Print a greeting message to the specified name.
    """
    print(f"Hello, {name}!")


def _log_build_choices(
    *, build_plan, dependency_collection, install_plan, log: Callable[[str], None]
) -> None:
    log(f"Building {build_plan.source_dir}")
    log(
        f"App entrypoint: {build_plan.entry_module}:{build_plan.entry_function} "
        f"({build_plan.app_source})"
    )
    log(
        f"Staged files: {len(build_plan.staged_files)} "
        f"({build_plan.staged_files_source})"
    )

    if dependency_collection.sources:
        log("Dependency sources:")
        for source in dependency_collection.sources:
            log(f"  - {source.label}: {_format_package_list(source.packages)}")
    else:
        log("Dependency sources: none")

    if dependency_collection.packages:
        log(
            "Resolved dependencies: "
            f"{_format_package_list(dependency_collection.packages)}"
        )
    else:
        log("Resolved dependencies: none")

    log("Install strategy:")
    log(f"  - pyodide.loadPackage: {_format_name_list(install_plan.pyodide_packages)}")
    log(f"  - micropip.install: {_format_name_list(install_plan.micropip_packages)}")


def _format_package_list(packages) -> str:
    if not packages:
        return "(none)"
    return ", ".join(str(package) for package in packages)


def _format_name_list(values: list[str]) -> str:
    if not values:
        return "(none)"
    return ", ".join(values)


if __name__ == "__main__":
    app()

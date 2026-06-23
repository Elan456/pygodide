import http.server
import socketserver
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
from pygodide.dep_handling.collection import collect_requirements

app = typer.Typer(name="Pygodide CLI", help="A command-line interface for Pygodide.")

DEFAULT_PYODIDE_PACKAGES = ["pygame-ce"]
DEFAULT_PYTHON_PATH_ENTRIES = ["/"]
DEFAULT_STAGED_FILES = ["main.py"]


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
    running_status_text: str = "Running",
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
        staged_files=resolved_staged_files,
        asset_base_path=asset_base_path,
        virtual_fs_root=virtual_fs_root,
        startup_python_code=resolved_startup_python_code,
        starting_pyodide_status_text=starting_pyodide_status_text,
        loading_packages_status_text=loading_packages_status_text,
        staging_files_status_text=staging_files_status_text,
        loading_app_status_text=loading_app_status_text,
        running_status_text=running_status_text,
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
):
    source_dir = path.resolve()
    try:
        build_plan = build_plan_for_source(source_dir, app_spec=app_spec)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    package_requirements = collect_requirements(source_dir)
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
        pyodide_packages=[],
        micropip_packages=[str(pkg) for pkg in package_requirements],
        python_path_entries=build_plan.python_path_entries,
        entry_module=build_plan.entry_module,
        entry_function=build_plan.entry_function,
    )

    boot_output_path = output_dir / boot_script_name
    boot_output_path.parent.mkdir(parents=True, exist_ok=True)
    boot_output_path.write_text(boot_js, encoding="utf-8")

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


if __name__ == "__main__":
    app()

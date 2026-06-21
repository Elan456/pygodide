from pathlib import Path
import shutil
from typing import Annotated

import typer
from jinja2 import Environment, PackageLoader, select_autoescape

import http.server
from functools import partial
import socketserver

app = typer.Typer(name="Pygodide CLI", help="A command-line interface for Pygodide.")

DEFAULT_PYODIDE_PACKAGES = ["pygame-ce"]
DEFAULT_PYTHON_FILES = ["main.py"]
DEFAULT_PYTHON_PATH_ENTRIES = ["/"]


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
    python_files: list[str] | None = None,
    python_path_entries: list[str] | None = None,
    asset_base_path: str = "./",
    virtual_fs_root: str = "/",
    entry_module: str = "main",
    entry_function: str = "main",
    startup_python_code: str | None = None,
    starting_pyodide_status_text: str = "Starting Pyodide...",
    loading_packages_status_text: str = "Loading Python packages...",
    staging_files_status_text: str = "Staging Python files...",
    loading_app_status_text: str = "Loading Python app...",
    running_status_text: str = "Running",
) -> str:
    template = _template_environment().get_template("boot.js")
    resolved_python_path_entries = python_path_entries or DEFAULT_PYTHON_PATH_ENTRIES
    resolved_startup_python_code = startup_python_code or _build_startup_python_code(
        entry_module=entry_module,
        entry_function=entry_function,
        python_path_entries=resolved_python_path_entries,
    )

    return template.render(
        status_element_id=status_element_id,
        canvas_element_id=canvas_element_id,
        pyodide_packages=pyodide_packages or DEFAULT_PYODIDE_PACKAGES,
        python_files=python_files or DEFAULT_PYTHON_FILES,
        asset_base_path=asset_base_path,
        virtual_fs_root=virtual_fs_root,
        startup_python_code=resolved_startup_python_code,
        starting_pyodide_status_text=starting_pyodide_status_text,
        loading_packages_status_text=loading_packages_status_text,
        staging_files_status_text=staging_files_status_text,
        loading_app_status_text=loading_app_status_text,
        running_status_text=running_status_text,
    )


def _default_title(source_dir: Path) -> str:
    if source_dir.name == "src" and source_dir.parent.name:
        return f"{source_dir.parent.name} Pyodide App"
    return f"{source_dir.name} Pyodide App"


def _discover_flat_files(source_dir: Path) -> list[Path]:
    return sorted(path for path in source_dir.iterdir() if path.is_file())


def _build_output_dir(path: Path) -> Path:
    resolved_path = path.resolve()
    if resolved_path.name == "build":
        return resolved_path
    return resolved_path.parent / "build"


@app.command()
def build(
    path: Annotated[Path, typer.Argument(help="Root directory of the Pygame app to build")],
    serve: bool = typer.Option(False, help="Whether to serve the built app after building")
):
    source_dir = path.resolve()
    if not source_dir.is_dir():
        raise typer.BadParameter(f"{source_dir} is not a directory")

    source_files = _discover_flat_files(source_dir)
    if not source_files:
        raise typer.BadParameter(f"{source_dir} does not contain any files to build")

    output_dir = _build_output_dir(source_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for source_file in source_files:
        shutil.copy2(source_file, output_dir / source_file.name)

    boot_script_name = "boot.js"
    index_html = render_index_html(
        title=_default_title(source_dir),
        boot_script_path=f"./{boot_script_name}",
    )

    index_output_path = output_dir / "index.html"
    index_output_path.write_text(index_html, encoding="utf-8")

    boot_js = render_boot_js(
        python_files=[source_file.name for source_file in source_files],
    )

    boot_output_path = output_dir / boot_script_name
    boot_output_path.parent.mkdir(parents=True, exist_ok=True)
    boot_output_path.write_text(boot_js, encoding="utf-8")

    if serve:
        _serve(output_dir)

@app.command()
def serve(
    path: Annotated[Path, typer.Argument(help="Source directory or build directory to serve")],
):
    """
    Serve the built Pygodide app from the build directory.
    """

    output_dir = _build_output_dir(path)
    if not output_dir.is_dir():
        raise RuntimeError(f"{output_dir} does not exist. Please run 'build' first.")

    _serve(output_dir)

def _serve(directory: Path, port: int = 8000):
    Handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))

    with socketserver.TCPServer(("", port), Handler) as httpd:
        print(f"Serving {directory} at http://localhost:{port}")
        httpd.serve_forever()


@app.command()
def hello(name: str):
    """
    Print a greeting message to the specified name.
    """
    print(f"Hello, {name}!")


if __name__ == "__main__":
    app()

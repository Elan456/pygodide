from __future__ import annotations

from jinja2 import Environment, PackageLoader, select_autoescape

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


def build_startup_python_code(
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
    resolved_startup_python_code = startup_python_code or build_startup_python_code(
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

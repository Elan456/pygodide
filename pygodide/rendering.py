from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from importlib import metadata
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

DEFAULT_PYODIDE_PACKAGES = ["pygame-ce"]
DEFAULT_PYTHON_PATH_ENTRIES = ["/"]
DEFAULT_PACKAGE_FILES = ["main.py"]
DEFAULT_READY_LOG = "[pygodide] ready"
# Must stay in sync with getHangHelpMessage() in templates/boot.js.
ASYNC_HANG_WARNING_PREFIX = "[pygodide] async hang:"


def package_version() -> str:
    """Installed pygodide version (from package metadata / pyproject)."""
    try:
        return metadata.version("pygodide")
    except metadata.PackageNotFoundError:
        return "0.0.0"


def content_cache_buster(content: str) -> str:
    """Short stable fingerprint for cache-busting generated static assets."""
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return digest[:12]


def package_files_cache_buster(directory: str | Path, package_files: list[str]) -> str:
    """Short fingerprint of packaged file paths + contents under DIRECTORY.

    Embedded in boot.js so asset URLs stay stable across reloads when the
    package set is unchanged, and change when any staged file changes.
    """
    root = Path(directory)
    hasher = hashlib.sha256()
    for relative_path in package_files:
        hasher.update(relative_path.encode("utf-8"))
        hasher.update(b"\0")
        path = root / relative_path
        if path.is_file():
            hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()[:12]


DEFAULT_FAVICON_NAME = "favicon.svg"
DEFAULT_FAVICON_MEDIA_TYPE = "image/svg+xml"
DEFAULT_LOGO_NAME = "pygodide-logo.svg"
# Prefer common root-level names; first match wins.
PROJECT_FAVICON_CANDIDATES = (
    "favicon.svg",
    "favicon.png",
    "favicon.ico",
    "favicon.webp",
    "favicon.jpg",
    "favicon.jpeg",
)
FAVICON_MEDIA_TYPES = {
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".webp": "image/webp",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}
# Canonical artwork lives in the docs site tree (also used for editable checkouts).
_DOCS_IMAGES = Path(__file__).resolve().parents[1] / "docs" / "assets" / "images"
_REPO_FAVICON = _DOCS_IMAGES / DEFAULT_FAVICON_NAME
_REPO_LOGO = _DOCS_IMAGES / DEFAULT_LOGO_NAME


@dataclass(frozen=True)
class ResolvedFavicon:
    """Favicon chosen for a build (project root file or bundled default)."""

    filename: str
    media_type: str
    source_path: Path | None
    source_label: str


def _template_environment() -> Environment:
    env = Environment(
        loader=PackageLoader("pygodide", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    # Emit Python string literals (single-quoted for normal paths).
    env.filters["py_repr"] = repr
    return env


def _package_svg(repo_path: Path, bundled_name: str) -> str:
    """Load SVG from the docs tree (editable) or the bundled wheel copy."""
    if repo_path.is_file():
        return repo_path.read_text(encoding="utf-8")
    return (
        files("pygodide")
        .joinpath("templates", bundled_name)
        .read_text(encoding="utf-8")
    )


def package_favicon_svg() -> str:
    """Return the browser-icon SVG used for built apps.

    Source of truth is ``docs/assets/images/favicon.svg``. Editable checkouts
    read that file directly; installed wheels use the copy bundled into the
    package via hatch ``force-include``.
    """
    return _package_svg(_REPO_FAVICON, DEFAULT_FAVICON_NAME)


def package_logo_svg() -> str:
    """Return the full wordmark SVG shown on the loading screen.

    Source of truth is ``docs/assets/images/pygodide-logo.svg``. Editable
    checkouts read that file directly; installed wheels use the copy bundled
    into the package via hatch ``force-include``.
    """
    return _package_svg(_REPO_LOGO, DEFAULT_LOGO_NAME)


def write_favicon(output_dir: Path, *, filename: str = DEFAULT_FAVICON_NAME) -> Path:
    """Write the package favicon into a build output directory."""
    destination = output_dir / filename
    destination.write_text(package_favicon_svg(), encoding="utf-8")
    return destination


def resolve_favicon(source_dir: Path) -> ResolvedFavicon:
    """Pick a project-root favicon if present, else the bundled default."""
    for filename in PROJECT_FAVICON_CANDIDATES:
        candidate = source_dir / filename
        if not candidate.is_file():
            continue
        media_type = FAVICON_MEDIA_TYPES.get(
            candidate.suffix.lower(),
            "application/octet-stream",
        )
        return ResolvedFavicon(
            filename=filename,
            media_type=media_type,
            source_path=candidate,
            source_label=f"project ({filename})",
        )
    return ResolvedFavicon(
        filename=DEFAULT_FAVICON_NAME,
        media_type=DEFAULT_FAVICON_MEDIA_TYPE,
        source_path=None,
        source_label="bundled default",
    )


def ensure_favicon(output_dir: Path, favicon: ResolvedFavicon) -> Path:
    """Write the resolved favicon into the build output directory."""
    destination = output_dir / favicon.filename
    if favicon.source_path is not None:
        shutil.copy2(favicon.source_path, destination)
        return destination
    return write_favicon(output_dir, filename=favicon.filename)


def write_logo(output_dir: Path, *, filename: str = DEFAULT_LOGO_NAME) -> Path:
    """Write the package loading logo into a build output directory."""
    destination = output_dir / filename
    destination.write_text(package_logo_svg(), encoding="utf-8")
    return destination


def render_index_html(
    *,
    title: str = "Pygame Pyodide Test",
    lang: str = "en",
    status_text: str = "Loading...",
    status_element_id: str = "status",
    canvas_element_id: str = "canvas",
    canvas_width: int = 800,
    canvas_height: int = 600,
    canvas_layout: str = "fixed",
    pyodide_url: str = "https://cdn.jsdelivr.net/pyodide/v314.0.0/full/pyodide.js",
    boot_script_path: str = "./boot.js",
    favicon_path: str = f"./{DEFAULT_FAVICON_NAME}",
    favicon_type: str = DEFAULT_FAVICON_MEDIA_TYPE,
    logo_path: str = f"./{DEFAULT_LOGO_NAME}",
    pygodide_version: str | None = None,
    boot_cache_buster: str | None = None,
) -> str:
    resolved_version = (
        package_version() if pygodide_version is None else pygodide_version
    )
    template = _template_environment().get_template("index.html")
    return template.render(
        title=title,
        lang=lang,
        status_text=status_text,
        status_element_id=status_element_id,
        canvas_element_id=canvas_element_id,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        canvas_layout=canvas_layout,
        pyodide_url=pyodide_url,
        boot_script_path=boot_script_path,
        favicon_path=favicon_path,
        favicon_type=favicon_type,
        logo_path=logo_path,
        pygodide_version=resolved_version,
        boot_cache_buster=boot_cache_buster or content_cache_buster(resolved_version),
    )


def build_startup_python_code(
    *,
    entry_module: str,
    entry_function: str,
    python_path_entries: list[str],
    virtual_fs_root: str = "/",
) -> str:
    """Render the in-browser Python glue that imports and runs the app entrypoint."""
    template = _template_environment().get_template("startup.py.j2")
    return (
        template.render(
            entry_module=entry_module,
            entry_function=entry_function,
            python_path_entries=python_path_entries,
            virtual_fs_root=virtual_fs_root,
        ).rstrip()
        + "\n"
    )


def render_boot_js(
    *,
    status_element_id: str = "status",
    canvas_element_id: str = "canvas",
    pyodide_packages: list[str] | None = None,
    micropip_packages: list[str] | None = None,
    declared_package_names: list[str] | None = None,
    package_files: list[str] | None = None,
    python_path_entries: list[str] | None = None,
    asset_base_path: str = "./",
    virtual_fs_root: str = "/",
    entry_module: str = "main",
    entry_function: str = "main",
    startup_python_code: str | None = None,
    starting_pyodide_status_text: str = "Starting Pyodide...",
    loading_packages_status_text: str = "Loading Python packages...",
    loading_files_status_text: str = "Loading app files...",
    loading_app_status_text: str = "Loading Python app...",
    running_status_text: str = "Running",
    ready_log: str = DEFAULT_READY_LOG,
    canvas_layout: str = "fixed",
    canvas_width: int = 800,
    canvas_height: int = 600,
    pygodide_version: str | None = None,
    asset_cache_buster: str | None = None,
) -> str:
    template = _template_environment().get_template("boot.js")
    if python_path_entries is None:
        resolved_python_path_entries = DEFAULT_PYTHON_PATH_ENTRIES
    else:
        resolved_python_path_entries = python_path_entries
    resolved_package_files = (
        package_files if package_files is not None else DEFAULT_PACKAGE_FILES
    )
    resolved_startup_python_code = startup_python_code or build_startup_python_code(
        entry_module=entry_module,
        entry_function=entry_function,
        python_path_entries=resolved_python_path_entries,
        virtual_fs_root=virtual_fs_root,
    )
    resolved_version = (
        package_version() if pygodide_version is None else pygodide_version
    )
    # Fallback keeps standalone render_boot_js callers working; builds pass a
    # content hash of the staged package files.
    resolved_asset_cache_buster = asset_cache_buster or content_cache_buster(
        "\n".join(resolved_package_files)
    )

    return template.render(
        status_element_id=status_element_id,
        canvas_element_id=canvas_element_id,
        canvas_layout=canvas_layout,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        pygodide_version=resolved_version,
        asset_cache_buster=resolved_asset_cache_buster,
        pyodide_packages=(
            pyodide_packages
            if pyodide_packages is not None
            else DEFAULT_PYODIDE_PACKAGES
        ),
        micropip_packages=micropip_packages if micropip_packages is not None else [],
        declared_package_names=(
            declared_package_names if declared_package_names is not None else []
        ),
        package_files=resolved_package_files,
        asset_base_path=asset_base_path,
        virtual_fs_root=virtual_fs_root,
        startup_python_code=resolved_startup_python_code,
        starting_pyodide_status_text=starting_pyodide_status_text,
        loading_packages_status_text=loading_packages_status_text,
        loading_files_status_text=loading_files_status_text,
        loading_app_status_text=loading_app_status_text,
        running_status_text=running_status_text,
        ready_log=ready_log,
    )

"""Bundle Pygame apps for the browser with Pyodide."""

from importlib import metadata

from pygodide.builder import BuildPlan, build_app

try:
    __version__ = metadata.version("pygodide")
except metadata.PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "BuildPlan",
    "build_app",
    "__version__",
]

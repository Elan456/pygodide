"""
This module handles picking the best way to install a dependency in pyodide.

Options (in order of priority):
1. ``pyodide.loadPackage`` for packages officially supported by pyodide
2. ``micropip.install()`` for packages on PyPI
"""

from __future__ import annotations

from .collection import parse_pyproject_dependencies
from .common import PackageInfo

__all__ = ["PackageInfo", "parse_pyproject_dependencies"]

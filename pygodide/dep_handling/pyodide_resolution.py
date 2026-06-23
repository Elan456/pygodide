"""
This module handles picking the best way to install a dependency in pyodide.

Options (in order of priority):
1. ``pyodide.loadPackage`` for packages officially supported by pyodide
2. ``micropip.install()`` for packages on PyPI
"""

from __future__ import annotations

from dataclasses import dataclass

from .collection import (
    DependencyCollection,
    DependencySource,
    collect_requirements,
    parse_dependency_groups,
    parse_pyproject_dependencies,
    parse_requirements_txt,
)
from .common import PackageInfo

DEFAULT_PYODIDE_PACKAGE_NAMES = {"pygame-ce"}


@dataclass(frozen=True)
class InstallPlan:
    pyodide_packages: list[str]
    micropip_packages: list[str]


def build_install_plan(packages: list[PackageInfo]) -> InstallPlan:
    pyodide_packages: list[str] = []
    micropip_packages: list[str] = []

    for package in packages:
        if package.normalized_name in DEFAULT_PYODIDE_PACKAGE_NAMES:
            pyodide_packages.append(package.name)
        else:
            micropip_packages.append(str(package))

    return InstallPlan(
        pyodide_packages=pyodide_packages,
        micropip_packages=micropip_packages,
    )


__all__ = [
    "DependencyCollection",
    "DependencySource",
    "InstallPlan",
    "PackageInfo",
    "build_install_plan",
    "collect_requirements",
    "parse_dependency_groups",
    "parse_pyproject_dependencies",
    "parse_requirements_txt",
]

"""
This module handles picking the best way to install a dependency in pyodide.

Options (in order of priority):
1. ``pyodide.loadPackage`` for packages officially supported by pyodide
2. ``micropip.install()`` for packages on PyPI
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet


@dataclass
class PackageInfo:
    name: str
    specifier: SpecifierSet | None = None


def parse_pyproject_dependencies(pyproject_path: str | Path) -> list[PackageInfo]:
    """Parse ``project.dependencies`` from a ``pyproject.toml`` file."""
    path = Path(pyproject_path)
    with path.open("rb") as pyproject_file:
        pyproject_data = tomllib.load(pyproject_file)

    raw_dependencies = pyproject_data.get("project", {}).get("dependencies", [])
    if raw_dependencies is None:
        return []
    if not isinstance(raw_dependencies, list):
        raise ValueError(
            f"{path} has a non-list [project].dependencies value: "
            f"{type(raw_dependencies).__name__}"
        )

    packages: list[PackageInfo] = []
    for dependency in raw_dependencies:
        if not isinstance(dependency, str):
            raise ValueError(
                f"{path} contains a non-string dependency entry: {dependency!r}"
            )

        try:
            requirement = Requirement(dependency)
        except InvalidRequirement as exc:
            raise ValueError(
                f"{path} contains an invalid dependency string: {dependency!r}"
            ) from exc

        specifier = requirement.specifier or None
        packages.append(PackageInfo(name=requirement.name, specifier=specifier))

    return packages


if __name__ == "__main__":
    print(parse_pyproject_dependencies("pyproject.toml"))

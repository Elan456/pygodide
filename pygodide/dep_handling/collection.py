"""
Collects the dependencies of a project
"""

from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement

from pygodide.pyproject import load_pyproject_data

from .common import PackageInfo


def collect_requirements(app_path: str | Path) -> list[PackageInfo]:
    """Collect the dependencies of a project by parsing its pyproject.toml file."""
    pyproject_path = Path(app_path) / "pyproject.toml"
    if not pyproject_path.is_file():
        return []

    return parse_pyproject_dependencies(pyproject_path)


def parse_pyproject_dependencies(pyproject_path: str | Path) -> list[PackageInfo]:
    """Parse ``project.dependencies`` from a ``pyproject.toml`` file."""
    path = Path(pyproject_path)
    pyproject_data = load_pyproject_data(path)
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

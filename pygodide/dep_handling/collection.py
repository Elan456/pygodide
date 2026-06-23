"""
Collect dependencies from the supported project configuration sources.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement

from pygodide.project_config import load_pygodide_project_config
from pygodide.pyproject import load_pyproject_data

from .common import PackageInfo


@dataclass(frozen=True)
class DependencySource:
    label: str
    packages: list[PackageInfo]


@dataclass(frozen=True)
class DependencyCollection:
    packages: list[PackageInfo]
    sources: list[DependencySource]


def collect_requirements(
    app_path: str | Path,
    *,
    extra_dependencies: list[str] | None = None,
) -> DependencyCollection:
    source_dir = Path(app_path)
    sources: list[DependencySource] = []

    requirements_path = source_dir / "requirements.txt"
    if requirements_path.is_file():
        packages = parse_requirements_txt(requirements_path)
        if packages:
            sources.append(
                DependencySource(label="requirements.txt", packages=packages)
            )

    pyproject_path = source_dir / "pyproject.toml"
    if pyproject_path.is_file():
        project_packages = parse_pyproject_dependencies(pyproject_path)
        if project_packages:
            sources.append(
                DependencySource(
                    label="[project].dependencies",
                    packages=project_packages,
                )
            )

        project_config = load_pygodide_project_config(source_dir)
        if project_config and project_config.dependencies:
            sources.append(
                DependencySource(
                    label="[tool.pygodide].dependencies",
                    packages=parse_dependency_strings(
                        project_config.dependencies,
                        source_label="[tool.pygodide].dependencies",
                        source_path=pyproject_path,
                    ),
                )
            )

        if project_config and project_config.dependency_groups:
            sources.extend(
                parse_dependency_groups(
                    pyproject_path,
                    group_names=project_config.dependency_groups,
                )
            )

    if extra_dependencies:
        sources.append(
            DependencySource(
                label="CLI --dep",
                packages=parse_dependency_strings(
                    extra_dependencies,
                    source_label="CLI --dep",
                ),
            )
        )

    return DependencyCollection(
        packages=merge_dependency_sources(sources),
        sources=sources,
    )


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

    return parse_dependency_strings(
        raw_dependencies,
        source_label="[project].dependencies",
        source_path=path,
    )


def parse_dependency_groups(
    pyproject_path: str | Path, *, group_names: list[str]
) -> list[DependencySource]:
    path = Path(pyproject_path)
    pyproject_data = load_pyproject_data(path)
    raw_groups = pyproject_data.get("dependency-groups", {})
    if not isinstance(raw_groups, dict):
        raise ValueError(
            f"{path} has a non-table [dependency-groups] value: "
            f"{type(raw_groups).__name__}"
        )

    sources: list[DependencySource] = []
    for group_name in group_names:
        raw_dependencies = raw_groups.get(group_name)
        if raw_dependencies is None:
            raise ValueError(
                f"{path} does not define dependency group {group_name!r} in "
                "[dependency-groups]"
            )
        if not isinstance(raw_dependencies, list):
            raise ValueError(
                f"{path} has a non-list [dependency-groups].{group_name} value: "
                f"{raw_dependencies!r}"
            )

        sources.append(
            DependencySource(
                label=f"[dependency-groups].{group_name}",
                packages=parse_dependency_strings(
                    raw_dependencies,
                    source_label=f"[dependency-groups].{group_name}",
                    source_path=path,
                ),
            )
        )

    return sources


def parse_requirements_txt(requirements_path: str | Path) -> list[PackageInfo]:
    path = Path(requirements_path)
    requirement_lines: list[str] = []

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            continue
        if stripped_line.startswith("-"):
            raise ValueError(
                f"{path}:{line_number} contains unsupported requirements.txt syntax: "
                f"{stripped_line!r}"
            )

        cleaned_line = stripped_line.split(" #", 1)[0].strip()
        if cleaned_line:
            requirement_lines.append(cleaned_line)

    return parse_dependency_strings(
        requirement_lines,
        source_label="requirements.txt",
        source_path=path,
    )


def parse_dependency_strings(
    dependencies: list[str],
    *,
    source_label: str,
    source_path: str | Path | None = None,
) -> list[PackageInfo]:
    packages: list[PackageInfo] = []
    for dependency in dependencies:
        source_display = str(source_path) if source_path is not None else source_label
        if not isinstance(dependency, str):
            raise ValueError(
                f"{source_display} contains a non-string dependency entry: "
                f"{dependency!r}"
            )

        try:
            requirement = Requirement(dependency)
        except InvalidRequirement as exc:
            raise ValueError(
                f"{source_display} contains an invalid dependency string: "
                f"{dependency!r}"
            ) from exc

        packages.append(
            PackageInfo(
                name=requirement.name,
                specifier=requirement.specifier or None,
            )
        )

    return packages


def merge_dependency_sources(sources: list[DependencySource]) -> list[PackageInfo]:
    merged_packages: dict[str, PackageInfo] = {}
    for source in sources:
        for package in source.packages:
            if package.normalized_name in merged_packages:
                del merged_packages[package.normalized_name]
            merged_packages[package.normalized_name] = package

    return list(merged_packages.values())

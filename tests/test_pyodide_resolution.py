import pytest
from packaging.specifiers import SpecifierSet

from pygodide.dep_handling.pyodide_resolution import (
    PackageInfo,
    parse_pyproject_dependencies,
)


def test_parse_pyproject_dependencies_reads_project_dependencies(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "demo"
version = "0.1.0"
dependencies = [
    "jinja2>=3.1.6",
    "pygame-ce",
]
""".strip(),
        encoding="utf-8",
    )

    dependencies = parse_pyproject_dependencies(pyproject)

    assert dependencies == [
        PackageInfo(name="jinja2", specifier=SpecifierSet(">=3.1.6")),
        PackageInfo(name="pygame-ce", specifier=None),
    ]


def test_parse_pyproject_dependencies_returns_empty_list_when_missing(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "demo"
version = "0.1.0"
""".strip(),
        encoding="utf-8",
    )

    assert parse_pyproject_dependencies(pyproject) == []


def test_parse_pyproject_dependencies_rejects_invalid_dependency_strings(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "demo"
version = "0.1.0"
dependencies = ["not valid @@"]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid dependency string"):
        parse_pyproject_dependencies(pyproject)

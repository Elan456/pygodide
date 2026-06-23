import pytest
from packaging.specifiers import SpecifierSet

from pygodide.dep_handling.pyodide_resolution import (
    PackageInfo,
    build_install_plan,
    collect_requirements,
    parse_pyproject_dependencies,
    parse_requirements_txt,
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


def test_parse_requirements_txt_reads_plain_requirements(tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        """
# comment
pygame-ce
numpy>=1.26 # inline comment
""".strip(),
        encoding="utf-8",
    )

    assert parse_requirements_txt(requirements) == [
        PackageInfo(name="pygame-ce", specifier=None),
        PackageInfo(name="numpy", specifier=SpecifierSet(">=1.26")),
    ]


def test_collect_requirements_merges_all_supported_sources(tmp_path):
    source_dir = tmp_path / "demo"
    source_dir.mkdir()
    (source_dir / "requirements.txt").write_text(
        "pygame-ce\nfastquadtree\n",
        encoding="utf-8",
    )
    (source_dir / "pyproject.toml").write_text(
        """
[project]
name = "demo"
version = "0.1.0"
dependencies = ["numpy>=1.26", "pygame-ce"]

[dependency-groups]
web = ["pillow", "numpy>=2.0"]

[tool.pygodide]
dependencies = ["pyyaml"]
dependency-groups = ["web"]
""".strip(),
        encoding="utf-8",
    )

    collection = collect_requirements(
        source_dir,
        extra_dependencies=["numpy>=2.1", "rich"],
    )

    assert [source.label for source in collection.sources] == [
        "requirements.txt",
        "[project].dependencies",
        "[tool.pygodide].dependencies",
        "[dependency-groups].web",
        "CLI --dep",
    ]
    assert collection.packages == [
        PackageInfo(name="fastquadtree", specifier=None),
        PackageInfo(name="pygame-ce", specifier=None),
        PackageInfo(name="pyyaml", specifier=None),
        PackageInfo(name="pillow", specifier=None),
        PackageInfo(name="numpy", specifier=SpecifierSet(">=2.1")),
        PackageInfo(name="rich", specifier=None),
    ]


def test_build_install_plan_splits_pyodide_and_micropip_packages():
    install_plan = build_install_plan(
        [
            PackageInfo(name="pygame-ce", specifier=None),
            PackageInfo(name="fastquadtree", specifier=None),
            PackageInfo(name="numpy", specifier=SpecifierSet(">=1.26")),
        ]
    )

    assert install_plan.pyodide_packages == ["pygame-ce"]
    assert install_plan.micropip_packages == ["fastquadtree", "numpy>=1.26"]

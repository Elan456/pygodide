import pytest

from pygodide.project_config import (
    AppEntrypoint,
    load_pygodide_project_config,
    parse_app_spec,
)


def test_parse_app_spec_reads_module_and_callable():
    assert parse_app_spec("game.main:web_main") == AppEntrypoint(
        module="game.main",
        callable_name="web_main",
    )


def test_parse_app_spec_rejects_invalid_format():
    with pytest.raises(ValueError, match="Expected format 'module:callable'"):
        parse_app_spec("main.py")


def test_load_pygodide_project_config_reads_tool_settings(tmp_path):
    source_dir = tmp_path / "demo"
    source_dir.mkdir()
    (source_dir / "pyproject.toml").write_text(
        """
[project]
name = "demo"
version = "0.1.0"

[tool.pygodide]
app = "main:web_main"
include = ["main.py", "assets/**"]
title = "Demo"
canvas-width = 900
canvas-height = 700
python-path = [".", "vendor"]
dependencies = ["pygame-ce", "fastquadtree"]
dependency-groups = ["web"]
""".strip(),
        encoding="utf-8",
    )

    config = load_pygodide_project_config(source_dir)

    assert config is not None
    assert config.app == AppEntrypoint(module="main", callable_name="web_main")
    assert config.include == ["main.py", "assets/**"]
    assert config.title == "Demo"
    assert config.canvas_width == 900
    assert config.canvas_height == 700
    assert config.python_path == [".", "vendor"]
    assert config.dependencies == ["pygame-ce", "fastquadtree"]
    assert config.dependency_groups == ["web"]

from pathlib import Path

from typer.testing import CliRunner

from pygodide.asyncify import (
    diagnose_entrypoint,
    format_smoke_async_warnings,
    resolve_auto_async,
)
from pygodide.building import build_plan_for_source
from pygodide.cli.main import app
from pygodide.project_config import load_pygodide_project_config

runner = CliRunner()


def test_load_pygodide_project_config_reads_auto_async(tmp_path):
    source_dir = tmp_path / "demo"
    source_dir.mkdir()
    (source_dir / "pyproject.toml").write_text(
        """
[project]
name = "demo"
version = "0.1.0"

[tool.pygodide]
auto-async = false
""".strip(),
        encoding="utf-8",
    )

    config = load_pygodide_project_config(source_dir)

    assert config is not None
    assert config.auto_async is False


def test_resolve_auto_async_prefers_cli_over_project_config(tmp_path):
    source_dir = tmp_path / "demo"
    source_dir.mkdir()
    (source_dir / "pyproject.toml").write_text(
        """
[project]
name = "demo"
version = "0.1.0"

[tool.pygodide]
auto-async = false
""".strip(),
        encoding="utf-8",
    )

    resolved, source = resolve_auto_async(source_dir, cli_auto_async=True)

    assert resolved is True
    assert source == "CLI --auto-async"


def test_resolve_auto_async_uses_project_config_when_cli_unset(tmp_path):
    source_dir = tmp_path / "demo"
    source_dir.mkdir()
    (source_dir / "pyproject.toml").write_text(
        """
[project]
name = "demo"
version = "0.1.0"

[tool.pygodide]
auto-async = false
""".strip(),
        encoding="utf-8",
    )

    resolved, source = resolve_auto_async(source_dir)

    assert resolved is False
    assert source == "[tool.pygodide].auto-async"


def test_build_command_uses_pyproject_auto_async_default(tmp_path):
    source_dir = _write_sync_pygame_app(tmp_path / "configured")
    (source_dir / "pyproject.toml").write_text(
        """
[project]
name = "configured"
version = "0.1.0"

[tool.pygodide]
auto-async = false
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["build", str(source_dir)])

    assert result.exit_code == 0, result.output
    assert "Auto-async setting: False ([tool.pygodide].auto-async)" in result.output
    assert "Auto async: disabled" in result.output

    built_main = (source_dir / "build" / "main.py").read_text(encoding="utf-8")
    assert "async def main" not in built_main


def test_smoke_warns_when_auto_async_disabled_for_sync_loop(tmp_path):
    source_dir = _write_sync_pygame_app(tmp_path / "sync_app")

    result = runner.invoke(
        app,
        ["smoke", str(source_dir), "--build-only", "--no-auto-async"],
    )

    assert result.exit_code == 0, result.output
    assert "Smoke warning: auto-async is disabled but the entrypoint looks" not in (
        result.output
    )
    smoke_log = (source_dir / "build" / "pygodide-smoke.log").read_text(
        encoding="utf-8"
    )
    assert "Pygodide smoke log" in smoke_log
    assert "Smoke warning: auto-async is disabled but the entrypoint looks" in smoke_log
    assert "Result: build-only success" in smoke_log


def test_format_smoke_async_warnings_for_unsafe_skip(tmp_path):
    source_dir = _write_sync_helper_without_loop(tmp_path / "unsafe")
    build_plan = build_plan_for_source(source_dir)
    diagnostic = diagnose_entrypoint(build_plan, source_dir)

    warnings = format_smoke_async_warnings(diagnostic, auto_async_enabled=True)

    assert len(warnings) == 1
    assert warnings[0].startswith("Smoke warning: auto-async cannot safely transform")


def _write_sync_pygame_app(source_dir: Path) -> Path:
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        """
import pygame

def main():
    while True:
        pygame.display.flip()
""".lstrip(),
        encoding="utf-8",
    )
    return source_dir


def _write_sync_helper_without_loop(source_dir: Path) -> Path:
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        """
def main():
    prepare()

def prepare():
    print("ready")
""".lstrip(),
        encoding="utf-8",
    )
    return source_dir

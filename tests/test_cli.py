import pytest
import typer
from typer.testing import CliRunner

from pygodide.cli.main import (
    ReusableTCPServer,
    _build_startup_python_code,
    app,
    build,
    render_boot_js,
    render_index_html,
)

runner = CliRunner()


def test_build_command_creates_expected_output(tmp_path):
    source_dir = tmp_path / "demo_app"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        "def main():\n    return None\n", encoding="utf-8"
    )
    (source_dir / "helpers.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source_dir / "testing_manifest.yaml").write_text(
        "name: demo-app\n", encoding="utf-8"
    )
    asset_dir = source_dir / "assets"
    asset_dir.mkdir()
    (asset_dir / "sprite.bin").write_bytes(b"\x00\x01\x02")
    generated_build_dir = source_dir / "build"
    generated_build_dir.mkdir()
    (generated_build_dir / "old.py").write_text("VALUE = 2\n", encoding="utf-8")
    venv_dir = source_dir / ".venv" / "bin"
    venv_dir.mkdir(parents=True)
    (venv_dir / "python").write_text("not a real interpreter\n", encoding="utf-8")

    result = runner.invoke(app, ["build", str(source_dir)])

    assert result.exit_code == 0, result.output
    assert "Building" in result.output
    assert "App entrypoint: main:main (default)" in result.output
    assert "Staged files: 3 (auto-discovery)" in result.output
    assert "Dependency sources: none" in result.output
    assert "Resolved dependencies: none" in result.output

    output_dir = source_dir / "build"
    assert output_dir.is_dir()
    assert (output_dir / "main.py").read_text(encoding="utf-8") == (
        source_dir / "main.py"
    ).read_text(encoding="utf-8")
    assert (output_dir / "helpers.py").read_text(encoding="utf-8") == (
        source_dir / "helpers.py"
    ).read_text(encoding="utf-8")
    assert (output_dir / "assets" / "sprite.bin").read_bytes() == b"\x00\x01\x02"
    assert not (output_dir / ".venv").exists()

    index_html = (output_dir / "index.html").read_text(encoding="utf-8")
    boot_js = (output_dir / "boot.js").read_text(encoding="utf-8")

    assert "<title>demo_app Pyodide App</title>" in index_html
    assert '<script type="module" src="./boot.js"></script>' in index_html
    assert '"assets/sprite.bin"' in boot_js
    assert '"helpers.py"' in boot_js
    assert '"main.py"' in boot_js
    assert "testing_manifest.yaml" not in boot_js
    assert "build/old.py" not in boot_js
    assert "from main import main" in boot_js


def test_build_command_rejects_empty_source_dir(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    with pytest.raises(typer.BadParameter, match="does not contain any files to build"):
        build(empty_dir)


def test_build_command_uses_tool_pygodide_config(tmp_path):
    source_dir = tmp_path / "configured_app"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        "async def web_main():\n    return None\n", encoding="utf-8"
    )
    (source_dir / "ball.py").write_text("VALUE = 1\n", encoding="utf-8")
    asset_dir = source_dir / "assets"
    asset_dir.mkdir()
    (asset_dir / "tone.dat").write_bytes(b"\x10\x20")
    (source_dir / "pyproject.toml").write_text(
        """
[project]
name = "configured-app"
version = "0.1.0"
dependencies = [
    "pygame-ce",
]

[tool.pygodide]
app = "main:web_main"
include = ["main.py", "assets/**"]
title = "Configured Game"
canvas-width = 1024
canvas-height = 768
python-path = [".", "vendor"]
dependencies = ["fastquadtree"]
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["build", str(source_dir)])

    assert result.exit_code == 0, result.output
    assert "App entrypoint: main:web_main ([tool.pygodide].app)" in result.output
    assert "Staged files: 2 ([tool.pygodide].include)" in result.output
    assert "[project].dependencies: pygame-ce" in result.output
    assert "[tool.pygodide].dependencies: fastquadtree" in result.output
    assert "pyodide.loadPackage: pygame-ce" in result.output
    assert "micropip.install: fastquadtree" in result.output

    output_dir = source_dir / "build"
    assert (output_dir / "main.py").is_file()
    assert not (output_dir / "ball.py").exists()
    assert (output_dir / "assets" / "tone.dat").read_bytes() == b"\x10\x20"

    index_html = (output_dir / "index.html").read_text(encoding="utf-8")
    boot_js = (output_dir / "boot.js").read_text(encoding="utf-8")

    assert "<title>Configured Game</title>" in index_html
    assert 'width="1024"' in index_html
    assert 'height="768"' in index_html
    assert 'const pyodidePackages = ["pygame-ce"];' in boot_js
    assert '"assets/tone.dat"' in boot_js
    assert "from main import web_main" in boot_js
    assert "/vendor" in boot_js


def test_build_command_cli_app_overrides_project_config(tmp_path):
    source_dir = tmp_path / "override_app"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        "async def web_main():\n    return None\n", encoding="utf-8"
    )
    (source_dir / "launcher.py").write_text(
        "def start():\n    return None\n", encoding="utf-8"
    )
    (source_dir / "pyproject.toml").write_text(
        """
[project]
name = "override-app"
version = "0.1.0"

[tool.pygodide]
app = "main:web_main"
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["build", str(source_dir), "--app", "launcher:start"])

    assert result.exit_code == 0, result.output
    assert "App entrypoint: launcher:start (CLI --app)" in result.output

    boot_js = (source_dir / "build" / "boot.js").read_text(encoding="utf-8")
    assert "from launcher import start" in boot_js
    assert "from main import web_main" not in boot_js


def test_build_command_accepts_requirements_txt_and_dep_flags(tmp_path):
    source_dir = tmp_path / "requirements_app"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        "def main():\n    return None\n", encoding="utf-8"
    )
    (source_dir / "requirements.txt").write_text(
        "pygame-ce\nnumpy>=1.26\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "build",
            str(source_dir),
            "--dep",
            "fastquadtree",
            "--dep",
            "rich",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "requirements.txt: pygame-ce, numpy>=1.26" in result.output
    assert "CLI --dep: fastquadtree, rich" in result.output
    assert (
        "Resolved dependencies: pygame-ce, numpy>=1.26, fastquadtree, rich"
        in result.output
    )
    assert "pyodide.loadPackage: pygame-ce" in result.output
    assert "micropip.install: numpy>=1.26, fastquadtree, rich" in result.output


def test_template_renderers_include_configured_values():
    startup_code = _build_startup_python_code(
        entry_module="demo.main",
        entry_function="start",
        python_path_entries=["/", "/vendor"],
    )
    index_html = render_index_html(title="Example", boot_script_path="./custom.js")
    boot_js = render_boot_js(
        pyodide_packages=["pygame-ce"],
        micropip_packages=["fastquadtree", "numpy>=1.26"],
        declared_package_names=["pygame-ce", "numpy"],
        staged_files=["main.py", "ball.py", "assets/theme.ogg"],
        python_path_entries=["/", "/vendor"],
        entry_module="demo.main",
        entry_function="start",
    )

    assert "<title>Example</title>" in index_html
    assert '<script type="module" src="./custom.js"></script>' in index_html
    assert 'class="pygodide-shell"' in index_html
    assert 'data-state="active"' in index_html
    assert "background: #090c17;" in index_html
    assert "border-radius" not in index_html
    assert "from demo.main import start" in startup_code
    assert "'/vendor'" in startup_code
    assert '"ball.py"' in boot_js
    assert '"assets/theme.ogg"' in boot_js
    assert 'const pyodidePackages = ["pygame-ce"];' in boot_js
    assert 'const micropipPackages = ["fastquadtree", "numpy\\u003e=1.26"];' in boot_js
    assert 'const declaredPackageNames = ["pygame-ce", "numpy"];' in boot_js
    assert "function formatPyodideError(error)" in boot_js
    assert "ModuleNotFoundError" in boot_js
    assert "Add '${suggestedPackageName}' to [project].dependencies" in boot_js
    assert 'pygame: "pygame-ce"' in boot_js
    assert "from demo.main import start" in boot_js
    assert "/vendor" in boot_js
    assert "await asyncio.sleep(0)" in boot_js
    assert "console.warn(getLoadingAppStatusMessage())" in boot_js
    assert "const appPromise = runtime.runPythonAsync(startupPythonCode);" in boot_js
    assert 'const readyLogMessage = "[pygodide] ready";' in boot_js
    assert "console.info(readyLogMessage)" in boot_js
    assert "status.dataset.state = state" in boot_js
    assert 'setStatus("", "hidden")' in boot_js
    assert "new Uint8Array(await response.arrayBuffer())" in boot_js
    assert 'cache: "no-store"' in boot_js
    assert 'url.searchParams.set("_pygodide", assetRequestCacheBuster)' in boot_js


def test_smoke_command_can_run_single_app_build_only(tmp_path):
    source_dir = tmp_path / "demo_app"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        "def main():\n    return None\n", encoding="utf-8"
    )

    result = runner.invoke(
        app,
        ["smoke", str(source_dir), "--build-only"],
    )

    assert result.exit_code == 0, result.output
    assert f"Building {source_dir}" in result.output
    assert "Smoke testing" not in result.output
    assert (source_dir / "build" / "index.html").is_file()


def test_smoke_command_can_run_target_suite_build_only(tmp_path):
    targets_root = tmp_path / "targets"
    target_dir = targets_root / "demo"
    target_dir.mkdir(parents=True)
    (target_dir / "main.py").write_text(
        "def main():\n    return None\n", encoding="utf-8"
    )
    (target_dir / "testing_manifest.yaml").write_text(
        "name: demo-target\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["smoke", str(targets_root), "--suite", "--build-only"],
    )

    assert result.exit_code == 0, result.output
    assert "Discovered 1 target(s)." in result.output
    assert "[demo-target] building" in result.output
    assert "[demo-target] passed" in result.output
    assert (target_dir / "build" / "index.html").is_file()


def test_compatibility_command_is_not_registered():
    result = runner.invoke(app, ["compatibility", "test_targets"])

    assert result.exit_code != 0
    assert "No such command 'compatibility'" in result.output


def test_dev_server_reuses_recently_closed_port():
    assert ReusableTCPServer.allow_reuse_address is True

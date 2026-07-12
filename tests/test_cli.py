from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from pygodide.cli.main import (
    app,
    build,
)
from pygodide.rendering import (
    build_startup_python_code,
    render_boot_js,
    render_index_html,
)
from pygodide.serving import ReusableTCPServer

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
    assert "Package files: 3 (auto-discovery)" in result.output
    assert "Dependency sources: none" in result.output
    assert "Resolved dependencies: none" in result.output

    output_dir = source_dir / "build"
    build_log = output_dir / "pygodide-build.log"
    assert output_dir.is_dir()
    assert build_log.is_file()
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
    favicon_svg = (output_dir / "favicon.svg").read_text(encoding="utf-8")

    assert "<title>demo_app Pyodide App</title>" in index_html
    assert '<script type="module" src="./boot.js"></script>' in index_html
    assert 'rel="icon" href="./favicon.svg"' in index_html
    assert 'id="pygodide-brand"' in index_html
    assert "pygodide-brand" in boot_js
    assert "viewBox" in favicon_svg
    assert '"assets/sprite.bin"' in boot_js
    assert '"helpers.py"' in boot_js
    assert '"main.py"' in boot_js
    assert "testing_manifest.yaml" not in boot_js
    assert "build/old.py" not in boot_js
    assert "from main import main" in boot_js

    build_log_text = build_log.read_text(encoding="utf-8")
    assert "Pygodide build log" in build_log_text
    assert f"Source directory: {source_dir}" in build_log_text
    assert "Build output:" in build_log_text
    assert "App entrypoint: main:main (default)" in build_log_text
    assert "Resolved dependencies: none" in build_log_text
    assert "Result: success" in build_log_text


def test_build_command_rejects_empty_source_dir(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    with pytest.raises(typer.BadParameter, match="does not contain any files to build"):
        build(empty_dir)

    build_log_text = (empty_dir / "build" / "pygodide-build.log").read_text(
        encoding="utf-8"
    )
    assert "Result: failure" in build_log_text
    assert "ValueError" in build_log_text
    assert "does not contain any files to build" in build_log_text
    assert "Traceback:" in build_log_text


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
    assert "Package files: 2 ([tool.pygodide].include)" in result.output
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
    startup_code = build_startup_python_code(
        entry_module="demo.main",
        entry_function="start",
        python_path_entries=["/", "/vendor"],
    )
    index_html = render_index_html(title="Example", boot_script_path="./custom.js")
    boot_js = render_boot_js(
        pyodide_packages=["pygame-ce"],
        micropip_packages=["fastquadtree", "numpy>=1.26"],
        declared_package_names=["pygame-ce", "numpy"],
        package_files=["main.py", "ball.py", "assets/theme.ogg"],
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
    assert "import os" in startup_code
    assert "os.chdir('/')" in startup_code
    assert "from demo.main import start" in startup_code
    assert "'/vendor'" in startup_code
    assert '"ball.py"' in boot_js
    assert '"assets/theme.ogg"' in boot_js
    assert 'const pyodidePackages = ["pygame-ce"];' in boot_js
    assert 'const micropipPackages = ["fastquadtree", "numpy\\u003e=1.26"];' in boot_js
    assert 'const declaredPackageNames = ["pygame-ce", "numpy"];' in boot_js
    assert "function extractPythonErrorText(error)" in boot_js
    assert "function formatPyodideError(error)" in boot_js
    assert "ModuleNotFoundError" in boot_js
    assert "Add '${suggestedPackageName}' to [project].dependencies" in boot_js
    assert 'pygame: "pygame-ce"' in boot_js
    assert "os.chdir(\\u0027/\\u0027)" in boot_js
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


def test_build_command_auto_asyncifies_sync_pygame_loop(tmp_path):
    source_dir = tmp_path / "sync_app"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        """
import pygame

def main():
    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
        pygame.display.update()
        clock.tick(60)
""".lstrip(),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["build", str(source_dir)])

    assert result.exit_code == 0, result.output
    assert "Auto async: transformed main.py, inserted await asyncio.sleep(0)" in (
        result.output
    )

    built_main = (source_dir / "build" / "main.py").read_text(encoding="utf-8")
    assert "async def main():" in built_main
    assert "await asyncio.sleep(0)" in built_main

    build_log = (source_dir / "build" / "pygodide-build.log").read_text(
        encoding="utf-8"
    )
    assert "Auto async: transformed main.py, inserted await asyncio.sleep(0)" in (
        build_log
    )
    assert "Auto async transformed source (main.py):" in build_log
    assert "await asyncio.sleep(0)" in build_log


def test_build_command_no_auto_async_leaves_sync_source(tmp_path):
    source_dir = tmp_path / "sync_app"
    source_dir.mkdir(parents=True)
    source_text = """
import pygame

def main():
    while True:
        pygame.display.flip()
""".lstrip()
    (source_dir / "main.py").write_text(source_text, encoding="utf-8")

    result = runner.invoke(app, ["build", str(source_dir), "--no-auto-async"])

    assert result.exit_code == 0, result.output
    assert "Auto async: disabled" in result.output

    built_main = (source_dir / "build" / "main.py").read_text(encoding="utf-8")
    assert built_main == (source_dir / "main.py").read_text(encoding="utf-8")
    assert "async def main" not in built_main

    build_log = (source_dir / "build" / "pygodide-build.log").read_text(
        encoding="utf-8"
    )
    assert "Auto-async: False" in build_log
    assert "Auto async: disabled" in build_log


def test_build_command_clean_removes_stale_build_files(tmp_path):
    source_dir = tmp_path / "demo_app"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        "async def main():\n    return None\n", encoding="utf-8"
    )

    build_dir = source_dir / "build"
    build_dir.mkdir()
    stale_file = build_dir / "old-asset.txt"
    stale_file.write_text("stale", encoding="utf-8")

    result = runner.invoke(app, ["build", str(source_dir), "--clean"])

    assert result.exit_code == 0, result.output
    assert not stale_file.exists()
    assert (build_dir / "index.html").is_file()


def test_build_command_zip_cleans_stale_build_files_without_clean_flag(tmp_path):
    source_dir = tmp_path / "demo_app"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        "async def main():\n    return None\n", encoding="utf-8"
    )

    build_dir = source_dir / "build"
    build_dir.mkdir()
    stale_file = build_dir / "old-asset.txt"
    stale_file.write_text("stale", encoding="utf-8")

    result = runner.invoke(app, ["build", str(source_dir), "--zip"])

    assert result.exit_code == 0, result.output
    assert not stale_file.exists()

    import zipfile

    with zipfile.ZipFile(source_dir / "demo_app.zip") as archive:
        assert "old-asset.txt" not in archive.namelist()


def test_build_command_creates_itch_zip(tmp_path):
    source_dir = tmp_path / "demo_app"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        "async def main():\n    return None\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["build", str(source_dir), "--zip"])

    assert result.exit_code == 0, result.output
    assert f"Created itch.io ZIP: {source_dir / 'demo_app.zip'}" in result.output

    zip_path = source_dir / "demo_app.zip"
    assert zip_path.is_file()

    import zipfile

    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()

    assert "index.html" in names
    assert "boot.js" in names
    assert all(not name.startswith("build/") for name in names)
    assert "pygodide-build.log" not in names


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
    assert f"Building {source_dir}" not in result.output
    assert "Smoke testing" not in result.output
    assert (source_dir / "build" / "index.html").is_file()

    smoke_log = source_dir / "build" / "pygodide-smoke.log"
    assert smoke_log.is_file()
    smoke_log_text = smoke_log.read_text(encoding="utf-8")
    assert "Pygodide smoke log" in smoke_log_text
    assert f"Source directory: {source_dir}" in smoke_log_text
    assert "Build only: True" in smoke_log_text
    assert "Build output:" in smoke_log_text
    assert "App entrypoint: main:main (default)" in smoke_log_text
    assert "Result: build-only success" in smoke_log_text


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
    assert "Discovered 1 target(s)." not in result.output
    assert "[demo-target] Smoke log:" not in result.output
    assert "[demo-target] Building" not in result.output
    assert "[demo-target] passed" in result.output
    assert (target_dir / "build" / "index.html").is_file()
    assert (target_dir / "build" / "pygodide-smoke.log").is_file()


def test_smoke_command_verbose_prints_build_details(tmp_path):
    source_dir = tmp_path / "demo_app"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        "def main():\n    return None\n", encoding="utf-8"
    )

    result = runner.invoke(
        app,
        ["smoke", str(source_dir), "--build-only", "--verbose"],
    )

    assert result.exit_code == 0, result.output
    assert "Smoke log:" in result.output
    assert f"Building {source_dir}" in result.output
    assert "App entrypoint: main:main (default)" in result.output


def test_serve_command_accepts_custom_port(tmp_path, monkeypatch):
    source_dir = tmp_path / "demo"
    build_dir = source_dir / "build"
    build_dir.mkdir(parents=True)
    (build_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    calls: list[tuple[Path, int]] = []

    def fake_serve(directory, *, port: int = 8000) -> None:
        calls.append((directory, port))

    monkeypatch.setattr(
        "pygodide.cli.runners.serve_directory_forever",
        fake_serve,
    )

    result = runner.invoke(app, ["serve", str(source_dir), "--port", "9000"])

    assert result.exit_code == 0, result.output
    assert calls == [(build_dir, 9000)]


def test_dev_server_reuses_recently_closed_port():
    assert ReusableTCPServer.allow_reuse_address is True

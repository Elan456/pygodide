import re
from importlib import metadata
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
    package_files_cache_buster,
    render_boot_js,
    render_index_html,
)
from pygodide.serving import ReusableTCPServer

runner = CliRunner()

# Rich error panels on narrow terminals (CI default width) wrap messages and
# inject ANSI codes around flags like --suite. Normalize before substring checks.
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
_BOX_DRAWING = str.maketrans(
    {
        "│": " ",
        "╭": " ",
        "╮": " ",
        "╰": " ",
        "╯": " ",
        "─": " ",
        "├": " ",
        "┤": " ",
        "┬": " ",
        "┴": " ",
        "┼": " ",
    }
)


def cli_text(output: str) -> str:
    """Strip ANSI/box art and collapse whitespace for stable CLI assertions."""
    plain = _ANSI_ESCAPE_RE.sub("", output).translate(_BOX_DRAWING)
    return " ".join(plain.split())


def test_version_option_matches_package_metadata():
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == f"pygodide {metadata.version('pygodide')}"


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
    git_objects = source_dir / ".git" / "objects" / "ab"
    git_objects.mkdir(parents=True)
    git_object = git_objects / "cdef"
    git_object.write_bytes(b"fake-git-object")
    git_object.chmod(0o444)
    github_workflow = source_dir / ".github" / "workflows"
    github_workflow.mkdir(parents=True)
    (github_workflow / "pages.yml").write_text("name: pages\n", encoding="utf-8")

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
    assert not (output_dir / ".git").exists()
    assert not (output_dir / ".github").exists()
    assert ".github/workflows/pages.yml" not in (output_dir / "boot.js").read_text(
        encoding="utf-8"
    )

    index_html = (output_dir / "index.html").read_text(encoding="utf-8")
    boot_js = (output_dir / "boot.js").read_text(encoding="utf-8")
    favicon_svg = (output_dir / "favicon.svg").read_text(encoding="utf-8")
    logo_svg = (output_dir / "pygodide-logo.svg").read_text(encoding="utf-8")

    assert "<title>demo_app Pyodide App</title>" in index_html
    assert 'src="./boot.js?v=' in index_html
    assert 'rel="icon" href="./favicon.svg"' in index_html
    assert 'id="pygodide-brand"' in index_html
    assert 'href="https://github.com/Elan456/pygodide"' in index_html
    assert 'id="pygodide-loader"' in index_html
    assert 'id="pygodide-progress"' in index_html
    assert 'id="pygodide-version"' in index_html
    assert f"pygodide {metadata.version('pygodide')}" in index_html
    assert 'src="./pygodide-logo.svg"' in index_html
    assert "pygodide-loader" in boot_js
    assert "LOADING_PROGRESS" in boot_js
    assert "setProgress" in boot_js
    assert f'const pygodideVersion = "{metadata.version("pygodide")}";' in boot_js
    assert "viewBox" in favicon_svg
    assert 'viewBox="12 9 326 102"' in logo_svg
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


def test_build_command_warns_when_source_looks_like_output_dir(tmp_path):
    project_dir = tmp_path / "my_game"
    build_dir = project_dir / "build"
    build_dir.mkdir(parents=True)
    (build_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (build_dir / "boot.js").write_text("// boot\n", encoding="utf-8")
    (build_dir / "main.py").write_text(
        "async def main():\n    return None\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["build", str(build_dir)])

    # Warning only — still attempts the build.
    combined = f"{result.output}\n{result.stderr}"
    assert "Warning:" in combined
    assert "previous pygodide build output" in combined
    assert "ignore this warning" in combined


def test_build_allows_project_directory_named_build(tmp_path):
    # A game whose folder is literally named "build" should work and not warn
    # just because of the name.
    source_dir = tmp_path / "build"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        "async def main():\n    return None\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["build", str(source_dir)])

    assert result.exit_code == 0, result.output
    combined = f"{result.output}\n{result.stderr}"
    assert "Warning:" not in combined
    assert (source_dir / "build" / "index.html").is_file()
    assert (source_dir / "build" / "boot.js").is_file()


def test_build_command_defaults_to_discovered_size_as_is(tmp_path):
    source_dir = tmp_path / "default_canvas"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        "async def main():\n    return None\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["build", str(source_dir)])

    assert result.exit_code == 0, result.output
    assert "Canvas aspect: not found" in result.output
    assert "using default 800x600" in result.output
    assert "Canvas: fixed 800x600 (as-is)" in result.output
    index_html = (source_dir / "build" / "index.html").read_text(encoding="utf-8")
    boot_js = (source_dir / "build" / "boot.js").read_text(encoding="utf-8")
    assert 'width="800"' in index_html
    assert 'height="600"' in index_html
    assert 'data-canvas-layout="fixed"' in index_html
    assert 'const canvasLayout = "fixed";' in boot_js


def test_build_command_logs_found_canvas_aspect_and_uses_as_is(tmp_path):
    source_dir = tmp_path / "aspect_found"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        """
import pygame

SCREEN_WIDTH, SCREEN_HEIGHT = 1024, 576
pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

async def main():
    return None
""".lstrip(),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["build", str(source_dir)])

    assert result.exit_code == 0, result.output
    assert "Canvas aspect: found 1024x576 in main.py" in result.output
    assert "Canvas: fixed 1024x576 (as-is)" in result.output
    index_html = (source_dir / "build" / "index.html").read_text(encoding="utf-8")
    assert 'width="1024"' in index_html
    assert 'height="576"' in index_html
    assert 'data-canvas-layout="fixed"' in index_html


def test_build_command_canvas_fit_scales_to_viewport(tmp_path):
    source_dir = tmp_path / "fit_canvas"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        """
import pygame
pygame.display.set_mode((800, 600))
async def main():
    return None
""".lstrip(),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["build", str(source_dir), "--canvas-fit"])

    assert result.exit_code == 0, result.output
    assert "Canvas: fit 800x600" in result.output
    index_html = (source_dir / "build" / "index.html").read_text(encoding="utf-8")
    boot_js = (source_dir / "build" / "boot.js").read_text(encoding="utf-8")
    assert 'data-canvas-layout="fit"' in index_html
    assert 'const canvasLayout = "fit";' in boot_js
    assert "sizeCanvasToFitAspect" in boot_js


def test_build_command_canvas_fit_with_explicit_size(tmp_path):
    source_dir = tmp_path / "fit_explicit"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        "async def main():\n    return None\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "build",
            str(source_dir),
            "--canvas-width",
            "960",
            "--canvas-height",
            "540",
            "--canvas-fit",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Canvas aspect: not found" in result.output
    assert "Canvas: fit 960x540" in result.output
    index_html = (source_dir / "build" / "index.html").read_text(encoding="utf-8")
    boot_js = (source_dir / "build" / "boot.js").read_text(encoding="utf-8")
    assert 'width="960"' in index_html
    assert 'height="540"' in index_html
    assert 'data-canvas-layout="fit"' in index_html
    assert "const canvasAspectWidth = 960;" in boot_js
    assert "const canvasAspectHeight = 540;" in boot_js
    assert 'const canvasLayout = "fit";' in boot_js


def test_build_command_canvas_fill_fills_viewport(tmp_path):
    source_dir = tmp_path / "fill_canvas"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        "async def main():\n    return None\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["build", str(source_dir), "--canvas-fill"])

    assert result.exit_code == 0, result.output
    assert "Canvas: fill viewport" in result.output
    index_html = (source_dir / "build" / "index.html").read_text(encoding="utf-8")
    boot_js = (source_dir / "build" / "boot.js").read_text(encoding="utf-8")
    assert 'data-canvas-layout="fill"' in index_html
    assert 'const canvasLayout = "fill";' in boot_js
    assert "sizeCanvasToViewport" in boot_js


def test_build_command_cli_canvas_size_overrides_project_config(tmp_path):
    source_dir = tmp_path / "canvas_app"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        "async def main():\n    return None\n",
        encoding="utf-8",
    )
    (source_dir / "pyproject.toml").write_text(
        """
[project]
name = "canvas-app"
version = "0.1.0"

[tool.pygodide]
canvas-width = 1024
canvas-height = 768
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "build",
            str(source_dir),
            "--canvas-width",
            "1280",
            "--canvas-height",
            "720",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Canvas: fixed 1280x720 (as-is)" in result.output
    index_html = (source_dir / "build" / "index.html").read_text(encoding="utf-8")
    boot_js = (source_dir / "build" / "boot.js").read_text(encoding="utf-8")
    assert 'width="1280"' in index_html
    assert 'height="720"' in index_html
    assert 'width="1024"' not in index_html
    assert 'data-canvas-layout="fixed"' in index_html
    assert 'const canvasLayout = "fixed";' in boot_js


def test_build_command_uses_project_root_favicon(tmp_path):
    source_dir = tmp_path / "icon_app"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        "async def main():\n    return None\n",
        encoding="utf-8",
    )
    project_icon = b"\x89PNG\r\n\x1a\ncustom-favicon"
    (source_dir / "favicon.png").write_bytes(project_icon)

    result = runner.invoke(app, ["build", str(source_dir)])

    assert result.exit_code == 0, result.output
    assert "Favicon: project (favicon.png)" in result.output

    output_dir = source_dir / "build"
    index_html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert 'rel="icon" href="./favicon.png"' in index_html
    assert 'type="image/png"' in index_html
    assert (output_dir / "favicon.png").read_bytes() == project_icon
    assert not (output_dir / "favicon.svg").exists()


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
    assert 'src="./custom.js?v=' in index_html
    assert 'class="pygodide-shell"' in index_html
    assert 'data-state="active"' in index_html
    assert "background: #090c17;" in index_html
    assert "pygodide-progress" in index_html
    assert "import os" in startup_code
    assert "import warnings" in startup_code
    assert "never awaited" in startup_code
    assert "os.chdir('/')" in startup_code
    assert "from demo.main import start" in startup_code
    assert "'/vendor'" in startup_code
    assert "pygodideMarkAppReady" in startup_code
    assert "pygodideWarnSyncEntrypoint" in startup_code
    assert "pygodideWarnAsyncHang" in startup_code
    assert "create_task" in startup_code
    assert "iscoroutinefunction" in startup_code
    assert '"ball.py"' in boot_js
    assert '"assets/theme.ogg"' in boot_js
    assert 'const pyodidePackages = ["pygame-ce"];' in boot_js
    assert 'const micropipPackages = ["fastquadtree", "numpy\\u003e=1.26"];' in boot_js
    assert 'const declaredPackageNames = ["pygame-ce", "numpy"];' in boot_js
    assert "function extractPythonErrorText(error)" in boot_js
    assert "function formatPyodideError(error)" in boot_js
    assert "function formatAssetFetchError(filename, url, detail)" in boot_js
    assert "Failed to download staged file" in boot_js
    assert "upload-pages-artifact always excludes .git and .github" in boot_js
    assert "stack.includes(message)" in boot_js
    assert "const pygodideVersion =" in boot_js
    assert "console.info(`pygodide ${pygodideVersion}`)" in boot_js
    assert "pygodide-version" in boot_js
    assert "ASSET_FETCH_CONCURRENCY" in boot_js
    assert "async function worker()" in boot_js
    assert "packageFiles[index]" in boot_js
    assert "ModuleNotFoundError" in boot_js
    assert "Add '${suggestedPackageName}' to [project].dependencies" in boot_js
    assert 'pygame: "pygame-ce"' in boot_js
    assert "os.chdir(\\u0027/\\u0027)" in boot_js
    assert "from demo.main import start" in boot_js
    assert "/vendor" in boot_js
    # Startup drains the event loop once (not frame pacing).
    assert ".sleep(0)" in boot_js
    # Loading-app hint for game loops.
    assert "await asyncio.sleep(1 / (60 * 2))" in boot_js
    assert "console.warn(getLoadingAppStatusMessage())" in boot_js
    assert "await runtime.runPythonAsync(startupPythonCode)" in boot_js
    assert 'const readyLogMessage = "[pygodide] ready";' in boot_js
    assert "console.info(readyLogMessage)" in boot_js
    assert "function markAppReady()" in boot_js
    assert "function warnSyncEntrypoint()" in boot_js
    assert "function warnAsyncHang()" in boot_js
    assert "function getAsyncHangHelpMessage()" in boot_js
    assert "pygodideMarkAppReady" in boot_js
    assert "pygodideWarnSyncEntrypoint" in boot_js
    assert "pygodideWarnAsyncHang" in boot_js
    assert "Your game entrypoint is synchronous" in boot_js
    assert "[pygodide] async hang:" in boot_js
    assert "forgotten await asyncio.sleep" in boot_js
    assert "app got stuck" in boot_js
    assert "status.dataset.state = state" in boot_js
    assert "function hideLoadingUi()" in boot_js
    assert 'setStatus("", "hidden")' in boot_js
    assert "new Uint8Array(await response.arrayBuffer())" in boot_js
    # Content-stable cache buster (not a per-load random value).
    assert "const assetRequestCacheBuster =" in boot_js
    assert "Date.now()" not in boot_js
    assert 'cache: "no-store"' not in boot_js
    assert 'url.searchParams.set("_pygodide", assetRequestCacheBuster)' in boot_js


def test_error_status_panel_is_interactive_scrollport():
    """Boot failure UI must accept pointer/wheel input and scroll long errors.

    The loader uses pointer-events: none while loading so the canvas stays
    clickable. On error, that must be lifted on the loader and status, and the
    canvas must not steal hits from the status scrollport.
    """
    index_html = render_index_html(title="Example", boot_script_path="./boot.js")
    boot_js = render_boot_js(
        pyodide_packages=["pygame-ce"],
        micropip_packages=[],
        declared_package_names=["pygame-ce"],
        package_files=["main.py"],
        python_path_entries=["/"],
        entry_module="main",
        entry_function="main",
    )

    # Loader: click-through while loading / hidden; interactive on error.
    assert "#pygodide-loader" in index_html
    assert re.search(
        r"#pygodide-loader\s*\{[^}]*pointer-events:\s*none",
        index_html,
        re.DOTALL,
    )
    assert re.search(
        r'#pygodide-loader\[data-state="hidden"\]\s*\{[^}]*pointer-events:\s*none',
        index_html,
        re.DOTALL,
    )
    assert re.search(
        r'#pygodide-loader\[data-state="error"\]\s*\{[^}]*pointer-events:\s*auto',
        index_html,
        re.DOTALL,
    )

    # Single error-panel scrollport (no competing max-height rules).
    error_blocks = re.findall(
        r'#status\[data-state="error"\]\s*\{([^}]+)\}',
        index_html,
    )
    assert len(error_blocks) == 1, (
        f"expected one #status[data-state=error] rule, found {len(error_blocks)}"
    )
    error_css = error_blocks[0]
    assert "pointer-events: auto" in error_css
    assert "user-select: text" in error_css
    assert "overflow-y: auto" in error_css
    assert "max-height:" in error_css
    assert "overscroll-behavior: contain" in error_css
    assert "flex: 0 0 auto" in error_css
    # Scrollbar affordance for long micropip/tracebacks.
    assert '#status[data-state="error"]::-webkit-scrollbar' in index_html
    assert "scrollbar-width: thin" in error_css

    # Loading chrome must still re-enable only the brand link, not the whole loader.
    assert re.search(
        r"#pygodide-brand\s*\{[^}]*pointer-events:\s*auto",
        index_html,
        re.DOTALL,
    )

    # boot.js disables canvas hit-testing while error chrome is shown.
    assert "function setCanvasPointerEventsForChrome(state)" in boot_js
    assert 'canvas.style.pointerEvents = "none"' in boot_js
    assert "setCanvasPointerEventsForChrome(chromeState)" in boot_js
    assert "function setLoadingChromeState(state)" in boot_js
    assert 'state === "error"' in boot_js


def test_package_files_cache_buster_stable_until_content_changes(tmp_path):
    root = tmp_path / "pkg"
    root.mkdir()
    (root / "main.py").write_text("print(1)\n", encoding="utf-8")
    assets = root / "assets"
    assets.mkdir()
    (assets / "sprite.png").write_bytes(b"\x89PNG\r\nfake")

    files = ["assets/sprite.png", "main.py"]
    first = package_files_cache_buster(root, files)
    second = package_files_cache_buster(root, files)
    assert first == second
    assert len(first) == 12

    (root / "main.py").write_text("print(2)\n", encoding="utf-8")
    assert package_files_cache_buster(root, files) != first


def test_build_embeds_package_content_cache_buster(tmp_path):
    source_dir = tmp_path / "cache_app"
    source_dir.mkdir()
    (source_dir / "main.py").write_text(
        "async def main():\n    return None\n",
        encoding="utf-8",
    )
    (source_dir / "data.txt").write_text("hello\n", encoding="utf-8")

    result = runner.invoke(app, ["build", str(source_dir)])
    assert result.exit_code == 0, result.output

    expected = package_files_cache_buster(
        source_dir / "build",
        ["data.txt", "main.py"],
    )
    boot_js = (source_dir / "build" / "boot.js").read_text(encoding="utf-8")
    assert f'const assetRequestCacheBuster = "{expected}";' in boot_js


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
    auto_async_msg = (
        "Auto async: transformed main.py, inserted await asyncio.sleep(1 / (60 * 2))"
    )
    assert auto_async_msg in result.output

    built_main = (source_dir / "build" / "main.py").read_text(encoding="utf-8")
    assert "async def main():" in built_main
    assert "await asyncio.sleep(1 / (60 * 2))" in built_main

    build_log = (source_dir / "build" / "pygodide-build.log").read_text(
        encoding="utf-8"
    )
    assert auto_async_msg in build_log
    assert "Auto async transformed source (main.py):" in build_log
    assert "await asyncio.sleep(1 / (60 * 2))" in build_log


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


def test_build_command_zip_does_not_recursively_include_previous_zip(tmp_path):
    """Repeated ``build --zip`` must not nest the prior ZIP inside the new one."""
    import zipfile

    source_dir = tmp_path / "demo_app"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        "async def main():\n    return None\n", encoding="utf-8"
    )

    first = runner.invoke(app, ["build", str(source_dir), "--zip"])
    assert first.exit_code == 0, first.output
    zip_path = source_dir / "demo_app.zip"
    first_size = zip_path.stat().st_size
    with zipfile.ZipFile(zip_path) as archive:
        first_names = set(archive.namelist())

    second = runner.invoke(app, ["build", str(source_dir), "--zip"])
    assert second.exit_code == 0, second.output
    second_size = zip_path.stat().st_size
    with zipfile.ZipFile(zip_path) as archive:
        second_names = set(archive.namelist())

    assert second_names == first_names
    assert "demo_app.zip" not in second_names
    # Allow small metadata jitter; recursive nesting would roughly double size.
    assert second_size < first_size * 1.5
    assert second_size < first_size + 50_000


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


def test_build_serve_accepts_custom_port(tmp_path, monkeypatch):
    source_dir = tmp_path / "demo"
    source_dir.mkdir()
    (source_dir / "main.py").write_text(
        "def main():\n    return None\n", encoding="utf-8"
    )
    calls: list[tuple[Path, int]] = []

    def fake_serve(directory, *, port: int = 8000) -> None:
        calls.append((directory, port))

    monkeypatch.setattr(
        "pygodide.cli.runners.serve_directory_forever",
        fake_serve,
    )

    result = runner.invoke(
        app,
        ["build", str(source_dir), "--serve", "--port", "9001"],
    )

    assert result.exit_code == 0, result.output
    assert calls == [(source_dir / "build", 9001)]


def test_build_warns_when_auto_async_disabled_on_sync_loop(tmp_path):
    source_dir = tmp_path / "demo"
    source_dir.mkdir()
    (source_dir / "main.py").write_text(
        """
import pygame

def main():
    screen = pygame.display.set_mode((800, 600))
    while True:
        for event in pygame.event.get():
            pass
        pygame.display.flip()
""".lstrip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["build", str(source_dir), "--no-auto-async"],
    )

    assert result.exit_code == 0, result.output
    assert "Auto async: disabled" in result.output
    assert "auto-async is disabled but the entrypoint looks like" in result.output
    boot_js = (source_dir / "build" / "boot.js").read_text(encoding="utf-8")
    assert "pygodideWarnSyncEntrypoint" in boot_js
    assert "Your game entrypoint is synchronous" in boot_js


def test_build_port_requires_serve(tmp_path):
    source_dir = tmp_path / "demo"
    source_dir.mkdir()
    (source_dir / "main.py").write_text(
        "def main():\n    return None\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["build", str(source_dir), "--port", "9000"])

    assert result.exit_code != 0
    assert "--port requires --serve" in cli_text(result.output)


def test_build_fails_when_entry_module_file_missing(tmp_path):
    source_dir = tmp_path / "demo"
    source_dir.mkdir()
    (source_dir / "other.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = runner.invoke(app, ["build", str(source_dir)])

    assert result.exit_code != 0
    output = cli_text(result.output)
    assert "Entry module file 'main.py' not found" in output
    assert "entrypoint 'main' from default" in output


def test_build_fails_when_entry_module_not_included(tmp_path):
    source_dir = tmp_path / "demo"
    source_dir.mkdir()
    (source_dir / "main.py").write_text(
        "def main():\n    return None\n", encoding="utf-8"
    )
    (source_dir / "extra.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source_dir / "pyproject.toml").write_text(
        """
[tool.pygodide]
include = ["extra.py"]
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["build", str(source_dir)])

    assert result.exit_code != 0
    output = cli_text(result.output)
    assert "not included in the build package" in output


def test_serve_missing_build_is_user_error(tmp_path):
    source_dir = tmp_path / "demo"
    source_dir.mkdir()

    result = runner.invoke(app, ["serve", str(source_dir)])

    assert result.exit_code != 0
    output = cli_text(result.output)
    assert "does not exist" in output
    assert "pygodide build" in output


def test_smoke_suite_rejects_single_app_flags(tmp_path):
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
        [
            "smoke",
            str(targets_root),
            "--suite",
            "--build-only",
            "--app",
            "main:main",
        ],
    )

    assert result.exit_code != 0
    output = cli_text(result.output)
    assert "Cannot combine --suite with single-app options" in output
    assert "--app" in output


def test_dev_server_reuses_recently_closed_port():
    assert ReusableTCPServer.allow_reuse_address is True

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
    source_dir = tmp_path / "demo_app" / "src"
    source_dir.mkdir(parents=True)
    (source_dir / "main.py").write_text(
        "def main():\n    return None\n", encoding="utf-8"
    )
    (source_dir / "helpers.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = runner.invoke(app, ["build", str(source_dir)])

    assert result.exit_code == 0, result.output

    output_dir = tmp_path / "demo_app" / "build"
    assert output_dir.is_dir()
    assert (output_dir / "main.py").read_text(encoding="utf-8") == (
        source_dir / "main.py"
    ).read_text(encoding="utf-8")
    assert (output_dir / "helpers.py").read_text(encoding="utf-8") == (
        source_dir / "helpers.py"
    ).read_text(encoding="utf-8")

    index_html = (output_dir / "index.html").read_text(encoding="utf-8")
    boot_js = (output_dir / "boot.js").read_text(encoding="utf-8")

    assert "<title>demo_app Pyodide App</title>" in index_html
    assert '<script type="module" src="./boot.js"></script>' in index_html
    assert '"helpers.py"' in boot_js
    assert '"main.py"' in boot_js
    assert "from main import main" in boot_js


def test_build_command_rejects_empty_source_dir(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    with pytest.raises(typer.BadParameter, match="does not contain any files to build"):
        build(empty_dir)


def test_template_renderers_include_configured_values():
    startup_code = _build_startup_python_code(
        entry_module="demo.main",
        entry_function="start",
        python_path_entries=["/", "/vendor"],
    )
    index_html = render_index_html(title="Example", boot_script_path="./custom.js")
    boot_js = render_boot_js(
        python_files=["main.py", "ball.py"],
        python_path_entries=["/", "/vendor"],
        entry_module="demo.main",
        entry_function="start",
    )

    assert "<title>Example</title>" in index_html
    assert '<script type="module" src="./custom.js"></script>' in index_html
    assert "from demo.main import start" in startup_code
    assert "'/vendor'" in startup_code
    assert '"ball.py"' in boot_js
    assert "from demo.main import start" in boot_js
    assert "/vendor" in boot_js
    assert 'cache: "no-store"' in boot_js
    assert 'url.searchParams.set("_pygodide", assetRequestCacheBuster)' in boot_js


def test_dev_server_reuses_recently_closed_port():
    assert ReusableTCPServer.allow_reuse_address is True

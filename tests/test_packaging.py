import zipfile

from pygodide.builder.zip import create_itch_zip, default_itch_zip_path


def test_default_itch_zip_path_uses_project_name(tmp_path):
    source_dir = tmp_path / "my-game"
    source_dir.mkdir()

    assert default_itch_zip_path(source_dir) == source_dir / "my-game.zip"


def test_create_itch_zip_puts_index_html_at_archive_root(tmp_path):
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (build_dir / "boot.js").write_text("export {}", encoding="utf-8")
    (build_dir / "pygodide-build.log").write_text("log", encoding="utf-8")

    zip_path = create_itch_zip(build_dir, tmp_path / "game.zip")

    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()

    assert names == ["boot.js", "index.html"]
    assert "pygodide-build.log" not in names

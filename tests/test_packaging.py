import zipfile

from pygodide.builder.plan import discover_package_files
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


def test_create_itch_zip_excludes_output_zip_but_keeps_asset_zips(tmp_path):
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (build_dir / "boot.js").write_text("export {}", encoding="utf-8")
    # Previous itch ZIP staged into build/ by mistake.
    (build_dir / "my-game.zip").write_bytes(b"PK\x03\x04stale")
    # Legitimate game asset archive should still ship.
    (build_dir / "assets").mkdir()
    (build_dir / "assets" / "data.zip").write_bytes(b"PK\x03\x04data")

    zip_path = create_itch_zip(build_dir, tmp_path / "my-game.zip")

    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()

    assert names == ["assets/data.zip", "boot.js", "index.html"]
    assert "my-game.zip" not in names


def test_discover_package_files_skips_itch_output_zips_only(tmp_path):
    source_dir = tmp_path / "my-game"
    source_dir.mkdir()
    (source_dir / "main.py").write_text("async def main():\n    return None\n")
    (source_dir / "my-game.zip").write_bytes(b"PK\x03\x04old")
    (source_dir / "build.zip").write_bytes(b"PK\x03\x04build")
    (source_dir / "assets").mkdir()
    (source_dir / "assets" / "data.zip").write_bytes(b"PK\x03\x04data")

    files = discover_package_files(source_dir)

    assert files == ["assets/data.zip", "main.py"]
    assert "my-game.zip" not in files
    assert "build.zip" not in files


def test_discover_package_files_skips_itch_zips_even_with_include_patterns(
    tmp_path,
):
    source_dir = tmp_path / "my-game"
    source_dir.mkdir()
    (source_dir / "main.py").write_text("async def main():\n    return None\n")
    (source_dir / "my-game.zip").write_bytes(b"PK\x03\x04old")
    (source_dir / "assets").mkdir()
    (source_dir / "assets" / "levels.zip").write_bytes(b"PK\x03\x04levels")

    files = discover_package_files(source_dir, include_patterns=["**"])

    assert files == ["assets/levels.zip", "main.py"]
    assert "my-game.zip" not in files

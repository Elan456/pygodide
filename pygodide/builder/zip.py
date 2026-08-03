from __future__ import annotations

import zipfile
from pathlib import Path

# Runtime archive fetched once by boot.js (not the itch.io upload zip).
APP_ARCHIVE_FILENAME = "app.zip"

ITCH_ZIP_EXCLUDED_FILENAMES = frozenset(
    {
        "pygodide-build.log",
        "pygodide-smoke.log",
    }
)


def default_itch_zip_path(source_dir: Path) -> Path:
    return source_dir.resolve() / f"{source_dir.name}.zip"


def create_app_archive(
    source_dir: Path,
    package_files: list[str],
    archive_path: Path,
) -> Path:
    """Write a DEFLATE zip of PACKAGE_FILES with project-relative member names.

    Members use stable posix paths (e.g. ``main.py``, ``assets/sprite.png``) so
    the browser unpack lands at the same paths games load locally.
    """
    resolved_source = Path(source_dir).resolve()
    resolved_archive = Path(archive_path).resolve()
    resolved_archive.parent.mkdir(parents=True, exist_ok=True)
    if resolved_archive.exists():
        resolved_archive.unlink()

    if not package_files:
        raise ValueError("Cannot create app archive: no package files")

    with zipfile.ZipFile(
        resolved_archive,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for relative_path in package_files:
            file_path = resolved_source / relative_path
            if not file_path.is_file():
                raise FileNotFoundError(
                    f"Package file {relative_path!r} not found under {resolved_source}"
                )
            # Always use forward-slash member names (zip standard / VFS paths).
            archive.write(file_path, arcname=relative_path.replace("\\", "/"))

    return resolved_archive


def remove_packaged_loose_files(
    output_dir: Path,
    package_files: list[str],
) -> None:
    """Remove loose copies of PACKAGE_FILES after they are archived.

    Keeps the published build from shipping both the zip and a full file tree
    (doubling itch/host payload). Shell files (boot.js, index.html, …) stay.
    """
    resolved_output = Path(output_dir).resolve()
    for relative_path in package_files:
        path = resolved_output / relative_path
        if path.is_file():
            path.unlink()

    # Prune empty directories bottom-up so nested asset folders disappear.
    dirs: set[Path] = set()
    for relative_path in package_files:
        parent = (resolved_output / relative_path).parent
        while parent != resolved_output and resolved_output in parent.parents:
            dirs.add(parent)
            parent = parent.parent
    for directory in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()


def create_itch_zip(build_dir: Path, zip_path: Path) -> Path:
    resolved_build_dir = build_dir.resolve()
    if not resolved_build_dir.is_dir():
        raise ValueError(f"{resolved_build_dir} is not a directory")

    index_html = resolved_build_dir / "index.html"
    if not index_html.is_file():
        raise ValueError(
            f"{resolved_build_dir} does not contain index.html. "
            "Run 'pygodide build' before creating a ZIP."
        )

    resolved_zip_path = zip_path.resolve()
    resolved_zip_path.parent.mkdir(parents=True, exist_ok=True)
    if resolved_zip_path.exists():
        resolved_zip_path.unlink()

    # Do not nest this archive (or a prior copy of it) inside itself.
    excluded_names = set(ITCH_ZIP_EXCLUDED_FILENAMES)
    excluded_names.add(resolved_zip_path.name)

    with zipfile.ZipFile(
        resolved_zip_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for file_path in sorted(resolved_build_dir.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.name in excluded_names:
                continue
            # If --zip-output points inside build/, do not pack the open archive.
            if file_path.resolve() == resolved_zip_path:
                continue
            archive.write(
                file_path,
                arcname=file_path.relative_to(resolved_build_dir).as_posix(),
            )

    return resolved_zip_path

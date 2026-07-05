from __future__ import annotations

import zipfile
from pathlib import Path

ITCH_ZIP_EXCLUDED_FILENAMES = frozenset(
    {
        "pygodide-build.log",
        "pygodide-smoke.log",
    }
)


def default_itch_zip_path(source_dir: Path) -> Path:
    return source_dir.resolve() / f"{source_dir.name}.zip"


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

    with zipfile.ZipFile(
        resolved_zip_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for file_path in sorted(resolved_build_dir.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.name in ITCH_ZIP_EXCLUDED_FILENAMES:
                continue
            archive.write(
                file_path,
                arcname=file_path.relative_to(resolved_build_dir).as_posix(),
            )

    return resolved_zip_path

from __future__ import annotations

import shutil
from pathlib import Path

from perf_benchmark.config import TARGET_SOURCE, WORK_ROOT


def prepare_work_copy(name: str) -> Path:
    if not TARGET_SOURCE.is_dir():
        raise FileNotFoundError(f"Benchmark target not found: {TARGET_SOURCE}")

    destination = WORK_ROOT / name
    if destination.exists():
        shutil.rmtree(destination)

    shutil.copytree(
        TARGET_SOURCE,
        destination,
        ignore=shutil.ignore_patterns("build", "__pycache__", "*.pyc"),
    )
    return destination

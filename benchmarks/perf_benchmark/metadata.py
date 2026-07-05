from __future__ import annotations

import importlib.metadata
import platform
import subprocess
import sys
from datetime import UTC, datetime
from typing import Any

from perf_benchmark.config import REPO_ROOT


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _repo_package_version(name: str) -> str | None:
    return _run_repo_python(
        f"import importlib.metadata; print(importlib.metadata.version({name!r}))"
    )


def _run_repo_python(code: str) -> str | None:
    completed = subprocess.run(
        ["uv", "run", "python", "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def collect_environment(
    *,
    browser_version: str | None = None,
    browser_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "benchmark_python": sys.version.split()[0],
        "pygame_ce_version": _run_repo_python(
            "import pygame; print(pygame.__version__)"
        ),
        "pygodide_version": _repo_package_version("pygodide"),
        "pygbag_version": _repo_package_version("pygbag"),
        "plotly_version": _package_version("plotly"),
        "playwright_version": _package_version("playwright"),
        "browser_version": browser_version,
        "browser_settings": browser_settings,
        "repo_root": str(REPO_ROOT),
    }

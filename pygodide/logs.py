from __future__ import annotations

import platform
import sys
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

from pygodide.builder.plan import build_output_dir

BUILD_LOG_FILENAME = "pygodide-build.log"
SMOKE_LOG_FILENAME = "pygodide-smoke.log"


def initialize_build_log(
    source_dir: Path,
    *,
    app_spec: str | None,
    deps: list[str] | None,
    serve: bool,
    auto_async: bool,
    canvas_width: int | None = None,
    canvas_height: int | None = None,
) -> Path:
    build_log_path = _build_log_path_for_source(source_dir)
    build_log_path.parent.mkdir(parents=True, exist_ok=True)
    build_log_path.write_text(
        "\n".join(
            [
                "Pygodide build log",
                f"Started: {_utc_timestamp()}",
                f"Pygodide version: {_pygodide_version()}",
                f"Python: {sys.version.splitlines()[0]}",
                f"Platform: {platform.platform()}",
                f"Working directory: {Path.cwd()}",
                f"Source directory: {source_dir}",
                f"Output directory: {build_log_path.parent}",
                f"Serve after build: {serve}",
                f"CLI app override: {app_spec or '(none)'}",
                f"CLI dependencies: {_format_cli_dependencies(deps)}",
                (
                    "CLI canvas-width: "
                    f"{canvas_width if canvas_width is not None else '(none)'}"
                ),
                (
                    "CLI canvas-height: "
                    f"{canvas_height if canvas_height is not None else '(none)'}"
                ),
                f"Auto-async: {auto_async}",
                "",
                "Build output:",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return build_log_path


def log_tee(
    log_path: Path,
    log: Callable[[str], None] | None = None,
) -> Callable[[str], None]:
    def write(message: str) -> None:
        if log is not None:
            log(message)
        append_log(log_path, message)

    return write


def build_log_tee(
    build_log_path: Path, log: Callable[[str], None]
) -> Callable[[str], None]:
    return log_tee(build_log_path, log)


def smoke_log_tee(
    smoke_log_path: Path, log: Callable[[str], None] | None = None
) -> Callable[[str], None]:
    return log_tee(smoke_log_path, log)


def write_build_log_success(build_log_path: Path) -> None:
    _write_log_success(build_log_path)


def write_build_log_failure(build_log_path: Path, exc: BaseException) -> None:
    _write_log_failure(build_log_path, exc)


def initialize_smoke_log(
    source_dir: Path,
    *,
    app_spec: str | None,
    deps: list[str] | None,
    auto_async: bool,
    auto_async_source: str,
    smoke_path: str,
    ready_log: str,
    timeout_ms: int,
    post_ready_ms: int,
    build_only: bool,
) -> Path:
    smoke_log_path = _smoke_log_path_for_source(source_dir)
    smoke_log_path.parent.mkdir(parents=True, exist_ok=True)
    smoke_log_path.write_text(
        "\n".join(
            [
                "Pygodide smoke log",
                f"Started: {_utc_timestamp()}",
                f"Pygodide version: {_pygodide_version()}",
                f"Python: {sys.version.splitlines()[0]}",
                f"Platform: {platform.platform()}",
                f"Working directory: {Path.cwd()}",
                f"Source directory: {source_dir}",
                f"Output directory: {smoke_log_path.parent}",
                f"Build only: {build_only}",
                f"CLI app override: {app_spec or '(none)'}",
                f"CLI dependencies: {_format_cli_dependencies(deps)}",
                f"Auto-async: {auto_async} ({auto_async_source})",
                f"Smoke path: {smoke_path}",
                f"Ready log: {ready_log}",
                f"Smoke timeout: {timeout_ms} ms",
                f"Post-ready listen: {post_ready_ms} ms",
                "",
                "Build output:",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return smoke_log_path


def write_smoke_log_success(smoke_log_path: Path, *, build_only: bool) -> None:
    result = "build-only success" if build_only else "success"
    _write_log_success(smoke_log_path, result=result)


def write_smoke_log_failure(smoke_log_path: Path, exc: BaseException) -> None:
    _write_log_failure(smoke_log_path, exc)


def append_build_log(build_log_path: Path, *lines: str) -> None:
    append_log(build_log_path, *lines)


def append_log(log_path: Path, *lines: str) -> None:
    with log_path.open("a", encoding="utf-8") as log_file:
        for line in lines:
            log_file.write(f"{line}\n")


def _write_log_success(log_path: Path, *, result: str = "success") -> None:
    append_log(
        log_path,
        "",
        f"Result: {result}",
        f"Finished: {_utc_timestamp()}",
    )


def _write_log_failure(log_path: Path, exc: BaseException) -> None:
    append_log(
        log_path,
        "",
        "Result: failure",
        f"Finished: {_utc_timestamp()}",
        f"Error: {type(exc).__name__}: {exc}",
        "",
        "Traceback:",
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip(),
    )


def log_build_choices(
    *, build_plan, dependency_collection, install_plan, log: Callable[[str], None]
) -> None:
    log(f"Building {build_plan.source_dir}")
    log(
        f"App entrypoint: {build_plan.entry_module}:{build_plan.entry_function} "
        f"({build_plan.app_source})"
    )
    if build_plan.canvas_width is None or build_plan.canvas_height is None:
        log("Canvas: auto (fill viewport)")
    else:
        log(f"Canvas: {build_plan.canvas_width}x{build_plan.canvas_height}")
    log(
        f"Package files: {len(build_plan.package_files)} "
        f"({build_plan.package_files_source})"
    )

    if dependency_collection.sources:
        log("Dependency sources:")
        for source in dependency_collection.sources:
            log(f"  - {source.label}: {_format_package_list(source.packages)}")
    else:
        log("Dependency sources: none")

    if dependency_collection.packages:
        log(
            "Resolved dependencies: "
            f"{_format_package_list(dependency_collection.packages)}"
        )
    else:
        log("Resolved dependencies: none")

    log("Install strategy:")
    log(f"  - pyodide.loadPackage: {_format_name_list(install_plan.pyodide_packages)}")
    log(f"  - micropip.install: {_format_name_list(install_plan.micropip_packages)}")


def _build_log_path_for_source(source_dir: Path) -> Path:
    if source_dir.is_dir():
        return build_output_dir(source_dir) / BUILD_LOG_FILENAME
    return Path.cwd() / BUILD_LOG_FILENAME


def _smoke_log_path_for_source(source_dir: Path) -> Path:
    if source_dir.is_dir():
        return build_output_dir(source_dir) / SMOKE_LOG_FILENAME
    return Path.cwd() / SMOKE_LOG_FILENAME


def _format_cli_dependencies(deps: list[str] | None) -> str:
    if not deps:
        return "(none)"
    return ", ".join(deps)


def _format_package_list(packages) -> str:
    if not packages:
        return "(none)"
    return ", ".join(str(package) for package in packages)


def _format_name_list(values: list[str]) -> str:
    if not values:
        return "(none)"
    return ", ".join(values)


def _pygodide_version() -> str:
    try:
        return metadata.version("pygodide")
    except metadata.PackageNotFoundError:
        return "(not installed)"


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()

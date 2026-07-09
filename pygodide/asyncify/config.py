from __future__ import annotations

from pathlib import Path

from pygodide.project_config import load_pygodide_project_config


def resolve_auto_async(
    source_dir: str | Path,
    *,
    cli_auto_async: bool | None = None,
    manifest_auto_async: bool | None = None,
) -> tuple[bool, str]:
    if cli_auto_async is not None:
        return (
            cli_auto_async,
            "CLI --auto-async" if cli_auto_async else "CLI --no-auto-async",
        )

    if manifest_auto_async is not None:
        return manifest_auto_async, "testing_manifest.yaml build.auto-async"

    project_config = load_pygodide_project_config(source_dir)
    if project_config is not None and project_config.auto_async is not None:
        return project_config.auto_async, "[tool.pygodide].auto-async"

    return True, "default"

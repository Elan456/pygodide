from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pygodide.pyproject import load_pyproject_data


@dataclass(frozen=True)
class AppEntrypoint:
    module: str
    callable_name: str


@dataclass(frozen=True)
class PygodideProjectConfig:
    app: AppEntrypoint | None = None
    include: list[str] | None = None
    title: str | None = None
    canvas_width: int | None = None
    canvas_height: int | None = None
    python_path: list[str] | None = None
    dependencies: list[str] | None = None
    dependency_groups: list[str] | None = None
    auto_async: bool | None = None


def parse_app_spec(app_spec: str) -> AppEntrypoint:
    module, separator, callable_name = app_spec.partition(":")
    if separator != ":" or not module or not callable_name:
        raise ValueError(
            f"Invalid app spec {app_spec!r}. Expected format 'module:callable'."
        )

    return AppEntrypoint(module=module, callable_name=callable_name)


def load_pygodide_project_config(
    source_dir: str | Path,
) -> PygodideProjectConfig | None:
    pyproject_path = Path(source_dir) / "pyproject.toml"
    if not pyproject_path.is_file():
        return None

    pyproject_data = load_pyproject_data(pyproject_path)
    raw_config = pyproject_data.get("tool", {}).get("pygodide")
    if raw_config is None:
        return None
    if not isinstance(raw_config, dict):
        raise ValueError(
            f"{pyproject_path} has a non-table [tool.pygodide] value: "
            f"{type(raw_config).__name__}"
        )

    return PygodideProjectConfig(
        app=_parse_optional_app(raw_config, pyproject_path),
        include=_parse_optional_string_list(
            raw_config,
            key="include",
            pyproject_path=pyproject_path,
        ),
        title=_parse_optional_string(
            raw_config,
            key="title",
            pyproject_path=pyproject_path,
        ),
        canvas_width=_parse_optional_int(
            raw_config,
            key="canvas-width",
            pyproject_path=pyproject_path,
        ),
        canvas_height=_parse_optional_int(
            raw_config,
            key="canvas-height",
            pyproject_path=pyproject_path,
        ),
        python_path=_parse_optional_string_list(
            raw_config,
            key="python-path",
            pyproject_path=pyproject_path,
        ),
        dependencies=_parse_optional_string_list(
            raw_config,
            key="dependencies",
            pyproject_path=pyproject_path,
        ),
        dependency_groups=_parse_optional_string_list(
            raw_config,
            key="dependency-groups",
            pyproject_path=pyproject_path,
        ),
        auto_async=_parse_optional_bool(
            raw_config,
            key="auto-async",
            pyproject_path=pyproject_path,
        ),
    )


def _parse_optional_app(
    raw_config: dict[str, Any], pyproject_path: Path
) -> AppEntrypoint | None:
    app_value = _parse_optional_string(
        raw_config,
        key="app",
        pyproject_path=pyproject_path,
    )
    if app_value is None:
        return None

    try:
        return parse_app_spec(app_value)
    except ValueError as exc:
        raise ValueError(f"{pyproject_path}: {exc}") from exc


def _parse_optional_string(
    raw_config: dict[str, Any], *, key: str, pyproject_path: Path
) -> str | None:
    value = raw_config.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(
            f"{pyproject_path} has a non-string [tool.pygodide].{key} value: {value!r}"
        )
    return value


def _parse_optional_bool(
    raw_config: dict[str, Any], *, key: str, pyproject_path: Path
) -> bool | None:
    value = raw_config.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(
            f"{pyproject_path} has a non-boolean [tool.pygodide].{key} value: {value!r}"
        )
    return value


def _parse_optional_int(
    raw_config: dict[str, Any], *, key: str, pyproject_path: Path
) -> int | None:
    value = raw_config.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(
            f"{pyproject_path} has a non-integer [tool.pygodide].{key} value: {value!r}"
        )
    return value


def _parse_optional_string_list(
    raw_config: dict[str, Any], *, key: str, pyproject_path: Path
) -> list[str] | None:
    value = raw_config.get(key)
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError(
            f"{pyproject_path} has a non-list [tool.pygodide].{key} value: {value!r}"
        )

    items: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            raise ValueError(
                f"{pyproject_path} contains a non-string entry in "
                f"[tool.pygodide].{key}: {entry!r}"
            )
        items.append(entry)

    return items

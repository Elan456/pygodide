from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from pygodide.rendering import DEFAULT_READY_LOG
from pygodide.smoke.types import (
    DEFAULT_POST_READY_MS,
    DEFAULT_SMOKE_PATH,
    DEFAULT_TIMEOUT_MS,
    DiscoveredTarget,
    SmokeConfig,
    TargetManifest,
)

MANIFEST_FILENAME = "testing_manifest.yaml"


def resolve_smoke_config(
    source_dir: str | Path,
    *,
    smoke: SmokeConfig | None = None,
) -> SmokeConfig:
    resolved_source_dir = Path(source_dir).resolve()
    cli_config = smoke or SmokeConfig()
    manifest_path = resolved_source_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        return cli_config

    manifest_smoke = load_target_manifest(resolved_source_dir).smoke
    return SmokeConfig(
        path=(
            cli_config.path
            if cli_config.path != DEFAULT_SMOKE_PATH
            else manifest_smoke.path
        ),
        ready_log=(
            cli_config.ready_log
            if cli_config.ready_log != DEFAULT_READY_LOG
            else manifest_smoke.ready_log
        ),
        timeout_ms=(
            cli_config.timeout_ms
            if cli_config.timeout_ms != DEFAULT_TIMEOUT_MS
            else manifest_smoke.timeout_ms
        ),
        post_ready_ms=(
            cli_config.post_ready_ms
            if cli_config.post_ready_ms != DEFAULT_POST_READY_MS
            else manifest_smoke.post_ready_ms
        ),
    )


def load_target_manifest(target_dir: str | Path) -> TargetManifest:
    resolved_target_dir = Path(target_dir).resolve()
    manifest_path = resolved_target_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise ValueError(f"{resolved_target_dir} is missing {MANIFEST_FILENAME}")

    try:
        raw_manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{manifest_path} is not valid YAML: {exc}") from exc

    if not isinstance(raw_manifest, dict):
        raise ValueError(f"{manifest_path} must contain a YAML mapping")

    allowed_keys = {"name", "description", "build", "smoke"}
    _reject_unknown_keys(raw_manifest, allowed_keys, manifest_path)

    name = _required_string(raw_manifest, "name", manifest_path)
    description = _optional_string(raw_manifest, "description", manifest_path)

    build_config = _optional_mapping(raw_manifest, "build", manifest_path)
    app_spec = None
    extra_dependencies = None
    auto_async = None
    if build_config is not None:
        _reject_unknown_keys(
            build_config,
            {"app", "deps", "auto-async"},
            manifest_path / "build",
        )
        app_spec = _optional_string(build_config, "app", manifest_path)
        extra_dependencies = _optional_string_list(build_config, "deps", manifest_path)
        auto_async = _optional_bool(build_config, "auto-async", manifest_path)

    smoke_config = _parse_smoke_config(raw_manifest, manifest_path)

    return TargetManifest(
        name=name,
        description=description,
        app_spec=app_spec,
        extra_dependencies=extra_dependencies,
        auto_async=auto_async,
        smoke=smoke_config,
    )


def discover_targets(
    root: str | Path,
    *,
    target_names: list[str] | None = None,
) -> list[DiscoveredTarget]:
    resolved_root = Path(root).resolve()
    if not resolved_root.is_dir():
        raise ValueError(f"{resolved_root} is not a directory")

    requested_names = set(target_names or [])
    discovered: list[DiscoveredTarget] = []
    manifest_names: set[str] = set()

    for target_dir in sorted(path for path in resolved_root.iterdir() if path.is_dir()):
        manifest = load_target_manifest(target_dir)
        if manifest.name in manifest_names:
            raise ValueError(f"Duplicate target manifest name: {manifest.name}")
        manifest_names.add(manifest.name)

        if requested_names and manifest.name not in requested_names:
            continue

        discovered.append(
            DiscoveredTarget(
                path=target_dir,
                manifest_path=target_dir / MANIFEST_FILENAME,
                manifest=manifest,
            )
        )

    if requested_names:
        missing = sorted(
            requested_names - {target.manifest.name for target in discovered}
        )
        if missing:
            raise ValueError(f"Unknown target name(s): {', '.join(missing)}")

    if not discovered:
        raise ValueError(f"{resolved_root} does not contain any test targets")

    return discovered


def _parse_smoke_config(
    raw_manifest: dict[str, Any], manifest_path: Path
) -> SmokeConfig:
    smoke_config = _optional_mapping(raw_manifest, "smoke", manifest_path)
    if smoke_config is None:
        return SmokeConfig()

    _reject_unknown_keys(
        smoke_config,
        {"path", "ready-log", "timeout-ms", "post-ready-ms"},
        manifest_path / "smoke",
    )
    path = _optional_string(smoke_config, "path", manifest_path) or DEFAULT_SMOKE_PATH
    if not path.startswith("/"):
        raise ValueError(f"{manifest_path}: smoke.path must start with '/'")

    return SmokeConfig(
        path=path,
        ready_log=(
            _optional_string(smoke_config, "ready-log", manifest_path)
            or DEFAULT_READY_LOG
        ),
        timeout_ms=_optional_positive_int(
            smoke_config,
            "timeout-ms",
            manifest_path,
            default=DEFAULT_TIMEOUT_MS,
        ),
        post_ready_ms=_optional_non_negative_int(
            smoke_config,
            "post-ready-ms",
            manifest_path,
            default=DEFAULT_POST_READY_MS,
        ),
    )


def _required_string(raw_data: dict[str, Any], key: str, source_path: Path) -> str:
    value = raw_data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{source_path}: {key} must be a non-empty string")
    return value


def _optional_bool(
    raw_data: dict[str, Any], key: str, source_path: Path
) -> bool | None:
    value = raw_data.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"{source_path}: {key} must be a boolean")
    return value


def _optional_string(
    raw_data: dict[str, Any], key: str, source_path: Path
) -> str | None:
    value = raw_data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{source_path}: {key} must be a string")
    return value


def _optional_string_list(
    raw_data: dict[str, Any], key: str, source_path: Path
) -> list[str] | None:
    value = raw_data.get(key)
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError(f"{source_path}: {key} must be a list of strings")

    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{source_path}: {key} must be a list of strings")
        items.append(item)
    return items


def _optional_mapping(
    raw_data: dict[str, Any], key: str, source_path: Path
) -> dict[str, Any] | None:
    value = raw_data.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{source_path}: {key} must be a mapping")
    return value


def _optional_positive_int(
    raw_data: dict[str, Any], key: str, source_path: Path, *, default: int
) -> int:
    value = raw_data.get(key, default)
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{source_path}: {key} must be a positive integer")
    return value


def _optional_non_negative_int(
    raw_data: dict[str, Any], key: str, source_path: Path, *, default: int
) -> int:
    value = raw_data.get(key, default)
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{source_path}: {key} must be a non-negative integer")
    return value


def _reject_unknown_keys(
    raw_data: dict[str, Any], allowed_keys: set[str], source_path: Path
) -> None:
    unknown_keys = sorted(str(key) for key in raw_data if key not in allowed_keys)
    if unknown_keys:
        raise ValueError(f"{source_path}: unknown key(s): {', '.join(unknown_keys)}")

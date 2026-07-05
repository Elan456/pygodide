from __future__ import annotations

import contextlib
import http.server
import shutil
import socketserver
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

import yaml

from pygodide.app_builder import build_app
from pygodide.asyncify import (
    diagnose_entrypoint,
    format_smoke_async_warnings,
    resolve_auto_async,
)
from pygodide.build_logging import (
    initialize_smoke_log,
    smoke_log_tee,
    write_smoke_log_failure,
    write_smoke_log_success,
)
from pygodide.building import build_output_dir, build_plan_for_source
from pygodide.rendering import DEFAULT_READY_LOG

MANIFEST_FILENAME = "testing_manifest.yaml"
DEFAULT_SMOKE_PATH = "/"
DEFAULT_TIMEOUT_MS = 120_000
DEFAULT_POST_READY_MS = 500
READY_STATUS_SELECTOR = '#status[data-state="hidden"]'


@dataclass(frozen=True)
class SmokeConfig:
    path: str = DEFAULT_SMOKE_PATH
    ready_log: str = DEFAULT_READY_LOG
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    post_ready_ms: int = DEFAULT_POST_READY_MS


@dataclass(frozen=True)
class TargetManifest:
    name: str
    description: str | None = None
    app_spec: str | None = None
    extra_dependencies: list[str] | None = None
    auto_async: bool | None = None
    smoke: SmokeConfig = SmokeConfig()


@dataclass(frozen=True)
class DiscoveredTarget:
    path: Path
    manifest_path: Path
    manifest: TargetManifest


@dataclass(frozen=True)
class CompatibilityResult:
    target_name: str
    target_path: Path
    build_dir: Path | None
    success: bool
    error: str | None = None


BuildRunner = Callable[[DiscoveredTarget], Path]
SmokeRunner = Callable[[DiscoveredTarget, Path], None]
Echo = Callable[[str], None]


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


def run_compatibility_suite(
    root: str | Path,
    *,
    target_names: list[str] | None = None,
    build_only: bool = False,
    build_runner: BuildRunner | None = None,
    smoke_runner: SmokeRunner | None = None,
    echo: Echo | None = None,
    verbose: bool = False,
) -> list[CompatibilityResult]:
    targets = discover_targets(root, target_names=target_names)
    resolved_build_runner = build_runner or build_target
    resolved_smoke_runner = smoke_runner or smoke_test_target
    results: list[CompatibilityResult] = []

    if verbose and echo is not None:
        echo(f"Discovered {len(targets)} target(s).")

    for target in targets:
        build_dir: Path | None = None
        try:
            if (
                resolved_build_runner is build_target
                and resolved_smoke_runner is smoke_test_target
            ):
                target_echo = None
                if verbose and echo is not None:
                    target_echo = _prefixed_echo(echo, target.manifest.name)
                build_dir = smoke_test_app(
                    target.path,
                    app_spec=target.manifest.app_spec,
                    deps=target.manifest.extra_dependencies,
                    smoke=target.manifest.smoke,
                    manifest_auto_async=target.manifest.auto_async,
                    build_only=build_only,
                    echo=target_echo,
                    verbose=verbose,
                )
            else:
                if echo is not None:
                    echo(f"[{target.manifest.name}] building")
                build_dir = resolved_build_runner(target)

                if not build_only:
                    if echo is not None:
                        echo(f"[{target.manifest.name}] smoke testing")
                    resolved_smoke_runner(target, build_dir)

            results.append(
                CompatibilityResult(
                    target_name=target.manifest.name,
                    target_path=target.path,
                    build_dir=build_dir,
                    success=True,
                )
            )
            if echo is not None:
                echo(f"[{target.manifest.name}] passed")
        except Exception as exc:
            results.append(
                CompatibilityResult(
                    target_name=target.manifest.name,
                    target_path=target.path,
                    build_dir=build_dir,
                    success=False,
                    error=str(exc),
                )
            )
            if echo is not None:
                echo(f"[{target.manifest.name}] failed: {exc}")

    return results


def smoke_test_app(
    source_dir: str | Path,
    *,
    app_spec: str | None = None,
    deps: list[str] | None = None,
    smoke: SmokeConfig | None = None,
    auto_async: bool | None = None,
    manifest_auto_async: bool | None = None,
    build_only: bool = False,
    clean_build: bool = True,
    echo: Echo | None = None,
    verbose: bool = False,
) -> Path:
    resolved_source_dir = Path(source_dir).resolve()
    smoke_config = resolve_smoke_config(resolved_source_dir, smoke=smoke)
    build_plan = build_plan_for_source(resolved_source_dir, app_spec=app_spec)
    resolved_auto_async, auto_async_source = resolve_auto_async(
        resolved_source_dir,
        cli_auto_async=auto_async,
        manifest_auto_async=manifest_auto_async,
    )

    if clean_build:
        output_dir = build_output_dir(resolved_source_dir)
        if output_dir.exists():
            shutil.rmtree(output_dir)

    smoke_log_path = initialize_smoke_log(
        resolved_source_dir,
        app_spec=app_spec,
        deps=deps,
        auto_async=resolved_auto_async,
        auto_async_source=auto_async_source,
        smoke_path=smoke_config.path,
        ready_log=smoke_config.ready_log,
        timeout_ms=smoke_config.timeout_ms,
        post_ready_ms=smoke_config.post_ready_ms,
        build_only=build_only,
    )
    console_log = echo if verbose else None
    log = smoke_log_tee(smoke_log_path, console_log)

    if verbose and echo is not None:
        echo(f"Smoke log: {smoke_log_path}")

    try:
        _log_smoke_async_warnings(
            build_plan,
            resolved_source_dir,
            auto_async_enabled=resolved_auto_async,
            log=log,
        )
        if auto_async_source != "default":
            log(f"Auto-async setting: {resolved_auto_async} ({auto_async_source})")

        build_dir = build_app(
            resolved_source_dir,
            app_spec=app_spec,
            deps=deps,
            auto_async=resolved_auto_async,
            log=log,
        )

        if build_only:
            write_smoke_log_success(smoke_log_path, build_only=True)
            return build_dir

        log("")
        log("Smoke output:")
        log(f"Smoke path: {smoke_config.path}")
        log(f"Ready log: {smoke_config.ready_log!r}")
        log(f"Timeout: {smoke_config.timeout_ms} ms")
        log("Smoke testing")

        with serve_directory(build_dir) as base_url:
            log(f"Serving build directory at {base_url}")
            run_playwright_smoke(smoke_config, base_url)

        log("Smoke test passed")
        write_smoke_log_success(smoke_log_path, build_only=False)
        return build_dir
    except Exception as exc:
        write_smoke_log_failure(smoke_log_path, exc)
        raise


def build_target(target: DiscoveredTarget, *, echo: Echo | None = None) -> Path:
    output_dir = build_output_dir(target.path)
    if output_dir.exists():
        shutil.rmtree(output_dir)

    build_plan = build_plan_for_source(
        target.path.resolve(),
        app_spec=target.manifest.app_spec,
    )
    resolved_auto_async, auto_async_source = resolve_auto_async(
        target.path.resolve(),
        manifest_auto_async=target.manifest.auto_async,
    )

    if echo is not None:
        _log_smoke_async_warnings(
            build_plan,
            target.path.resolve(),
            auto_async_enabled=resolved_auto_async,
            log=echo,
        )
        if auto_async_source != "default":
            echo(f"Auto-async setting: {resolved_auto_async} ({auto_async_source})")

    return build_app(
        target.path.resolve(),
        app_spec=target.manifest.app_spec,
        deps=target.manifest.extra_dependencies,
        auto_async=resolved_auto_async,
        log=None,
    )


def smoke_test_target(target: DiscoveredTarget, build_dir: Path) -> None:
    with serve_directory(build_dir) as base_url:
        run_playwright_smoke(target.manifest.smoke, base_url)


def _prefixed_echo(echo: Echo, prefix: str) -> Echo:
    return lambda message: echo(f"[{prefix}] {message}")


def _log_smoke_async_warnings(
    build_plan,
    source_dir: Path,
    *,
    auto_async_enabled: bool,
    log: Echo,
) -> None:
    diagnostic = diagnose_entrypoint(build_plan, source_dir)
    for warning in format_smoke_async_warnings(
        diagnostic,
        auto_async_enabled=auto_async_enabled,
    ):
        log(warning)


@contextlib.contextmanager
def serve_directory(directory: str | Path) -> Iterator[str]:
    resolved_directory = Path(directory).resolve()
    if not resolved_directory.is_dir():
        raise ValueError(f"{resolved_directory} is not a directory")

    handler = partial(NoCacheHTTPRequestHandler, directory=str(resolved_directory))
    with ReusableTCPServer(("127.0.0.1", 0), handler) as httpd:
        host, port = httpd.server_address
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        try:
            yield f"http://{host}:{port}"
        finally:
            httpd.shutdown()
            server_thread.join(timeout=5)


def run_playwright_smoke(smoke: SmokeConfig, base_url: str) -> None:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Playwright is not installed. Install dev dependencies and browsers with "
            "'uv sync --dev' and 'uv run playwright install chromium'."
        ) from exc

    ready_seen = threading.Event()
    failures: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()

        def handle_console(message) -> None:
            text = message.text
            if text == smoke.ready_log:
                ready_seen.set()
            if message.type == "error":
                failures.append(f"console error: {text}")

        page.on("console", handle_console)
        page.on("pageerror", lambda exc: failures.append(f"page error: {exc}"))

        try:
            page.goto(_join_url(base_url, smoke.path), wait_until="domcontentloaded")
            deadline = time.monotonic() + smoke.timeout_ms / 1000
            while not ready_seen.is_set() and not failures:
                if time.monotonic() >= deadline:
                    break
                page.wait_for_timeout(100)

            if ready_seen.is_set() and not failures:
                try:
                    _assert_ready_status_hidden(
                        page,
                        timeout_ms=_remaining_timeout_ms(deadline),
                        timeout_error=PlaywrightTimeoutError,
                    )
                except RuntimeError as exc:
                    failures.append(str(exc))
                else:
                    page.wait_for_timeout(smoke.post_ready_ms)
        finally:
            browser.close()

    if failures:
        raise RuntimeError("; ".join(failures))
    if not ready_seen.is_set():
        raise RuntimeError(
            f"Timed out waiting for ready log {smoke.ready_log!r} "
            f"after {smoke.timeout_ms} ms"
        )


def _remaining_timeout_ms(deadline: float) -> int:
    return max(1, int((deadline - time.monotonic()) * 1000))


def _assert_ready_status_hidden(
    page: Any,
    *,
    timeout_ms: int,
    timeout_error: type[BaseException],
) -> None:
    try:
        page.wait_for_selector(READY_STATUS_SELECTOR, timeout=max(timeout_ms, 1))
    except timeout_error as exc:
        raise RuntimeError(
            "Page logged ready but did not hide the loading status. "
            "The app may be blocking the browser event loop; make the entrypoint "
            "async and yield with await asyncio.sleep(0) in long-running loops."
        ) from exc


class NoCacheHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format: str, *args) -> None:
        return


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


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


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

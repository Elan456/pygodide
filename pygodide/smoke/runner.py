from __future__ import annotations

from pathlib import Path

from pygodide.asyncify import (
    diagnose_entrypoint,
    format_smoke_async_warnings,
    resolve_auto_async,
)
from pygodide.builder.pipeline import build_app
from pygodide.builder.plan import build_plan_for_source, clean_build_dir
from pygodide.logs import (
    initialize_smoke_log,
    smoke_log_tee,
    write_smoke_log_failure,
    write_smoke_log_success,
)
from pygodide.serving import serve_directory
from pygodide.smoke.manifest import discover_targets, resolve_smoke_config
from pygodide.smoke.playwright_smoke import run_playwright_smoke
from pygodide.smoke.types import (
    BuildRunner,
    DiscoveredTarget,
    Echo,
    SmokeConfig,
    SmokeRunner,
    SmokeSuiteResult,
)


def run_smoke_suite(
    root: str | Path,
    *,
    target_names: list[str] | None = None,
    build_only: bool = False,
    build_runner: BuildRunner | None = None,
    smoke_runner: SmokeRunner | None = None,
    echo: Echo | None = None,
    verbose: bool = False,
) -> list[SmokeSuiteResult]:
    targets = discover_targets(root, target_names=target_names)
    resolved_build_runner = build_runner or build_target
    resolved_smoke_runner = smoke_runner or smoke_test_target
    results: list[SmokeSuiteResult] = []

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
                SmokeSuiteResult(
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
                SmokeSuiteResult(
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
    canvas_width: int | None = None,
    canvas_height: int | None = None,
    build_only: bool = False,
    clean_build: bool = True,
    echo: Echo | None = None,
    verbose: bool = False,
) -> Path:
    resolved_source_dir = Path(source_dir).resolve()
    smoke_config = resolve_smoke_config(resolved_source_dir, smoke=smoke)
    build_plan = build_plan_for_source(
        resolved_source_dir,
        app_spec=app_spec,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )
    resolved_auto_async, auto_async_source = resolve_auto_async(
        resolved_source_dir,
        cli_auto_async=auto_async,
        manifest_auto_async=manifest_auto_async,
    )

    if clean_build:
        clean_build_dir(resolved_source_dir)

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
            canvas_width=canvas_width,
            canvas_height=canvas_height,
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
    clean_build_dir(target.path)

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

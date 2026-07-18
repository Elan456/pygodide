from __future__ import annotations

from pathlib import Path

import pytest

from pygodide.rendering import ASYNC_HANG_WARNING_PREFIX, build_startup_python_code
from pygodide.smoke import (
    MANIFEST_FILENAME,
    DiscoveredTarget,
    SmokeConfig,
    SmokeObservation,
    TargetManifest,
    assert_ready_status_hidden,
    discover_targets,
    evaluate_smoke_result,
    load_target_manifest,
    remaining_timeout_ms,
    resolve_smoke_config,
    run_smoke_suite,
)


def test_load_target_manifest_reads_yaml_metadata(tmp_path):
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / MANIFEST_FILENAME).write_text(
        """
name: demo-target
description: Exercises custom target metadata.
build:
  app: launcher:start
  deps:
    - pygame-ce
smoke:
  path: /index.html
  ready-log: "custom ready"
  timeout-ms: 45000
  post-ready-ms: 250
""".strip(),
        encoding="utf-8",
    )

    manifest = load_target_manifest(target_dir)

    assert manifest == TargetManifest(
        name="demo-target",
        description="Exercises custom target metadata.",
        app_spec="launcher:start",
        extra_dependencies=["pygame-ce"],
        smoke=SmokeConfig(
            path="/index.html",
            ready_log="custom ready",
            timeout_ms=45000,
            post_ready_ms=250,
        ),
    )


def test_load_target_manifest_rejects_missing_manifest(tmp_path):
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    with pytest.raises(ValueError, match="missing testing_manifest.yaml"):
        load_target_manifest(target_dir)


def test_load_target_manifest_rejects_malformed_metadata(tmp_path):
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / MANIFEST_FILENAME).write_text(
        """
name: demo-target
smoke:
  path: relative.html
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="smoke.path must start with '/'"):
        load_target_manifest(target_dir)


def test_discover_targets_requires_manifest_for_each_target_dir(tmp_path):
    valid_target = tmp_path / "valid"
    valid_target.mkdir()
    (valid_target / MANIFEST_FILENAME).write_text(
        "name: valid-target\n",
        encoding="utf-8",
    )
    missing_manifest = tmp_path / "missing"
    missing_manifest.mkdir()

    with pytest.raises(ValueError, match="missing testing_manifest.yaml"):
        discover_targets(tmp_path)


def test_discover_targets_filters_by_manifest_name(tmp_path):
    _write_target_manifest(tmp_path / "first", "first-target")
    _write_target_manifest(tmp_path / "second", "second-target")

    targets = discover_targets(tmp_path, target_names=["second-target"])

    assert [target.manifest.name for target in targets] == ["second-target"]


def test_run_smoke_suite_uses_injected_build_and_smoke_runners(tmp_path):
    target_dir = _write_target_manifest(tmp_path / "demo", "demo-target")
    calls: list[tuple[str, str]] = []

    def build_runner(target: DiscoveredTarget) -> Path:
        calls.append(("build", target.manifest.name))
        build_dir = target.path / "build"
        build_dir.mkdir()
        return build_dir

    def smoke_runner(target: DiscoveredTarget, build_dir: Path) -> None:
        assert build_dir == target_dir / "build"
        calls.append(("smoke", target.manifest.name))

    results = run_smoke_suite(
        tmp_path,
        build_runner=build_runner,
        smoke_runner=smoke_runner,
    )

    assert [result.success for result in results] == [True]
    assert calls == [("build", "demo-target"), ("smoke", "demo-target")]


def test_run_smoke_suite_reports_target_failures(tmp_path):
    _write_target_manifest(tmp_path / "demo", "demo-target")

    def build_runner(target: DiscoveredTarget) -> Path:
        raise RuntimeError(f"{target.manifest.name} build failed")

    results = run_smoke_suite(tmp_path, build_runner=build_runner)

    assert len(results) == 1
    assert results[0].success is False
    assert results[0].error == "demo-target build failed"


def test_load_target_manifest_reads_build_auto_async(tmp_path):
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / MANIFEST_FILENAME).write_text(
        """
name: demo-target
build:
  auto-async: false
""".strip(),
        encoding="utf-8",
    )

    manifest = load_target_manifest(target_dir)

    assert manifest.auto_async is False


def test_resolve_smoke_config_uses_manifest_defaults(tmp_path):
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / MANIFEST_FILENAME).write_text(
        """
name: demo-target
smoke:
  path: /index.html
  timeout-ms: 180000
""".strip(),
        encoding="utf-8",
    )

    config = resolve_smoke_config(target_dir)

    assert config == SmokeConfig(path="/index.html", timeout_ms=180000)


def test_resolve_smoke_config_keeps_explicit_cli_overrides(tmp_path):
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / MANIFEST_FILENAME).write_text(
        """
name: demo-target
smoke:
  timeout-ms: 180000
""".strip(),
        encoding="utf-8",
    )

    config = resolve_smoke_config(
        target_dir,
        smoke=SmokeConfig(timeout_ms=45000),
    )

    assert config.timeout_ms == 45000


def test_remaining_timeout_ms_uses_deadline_budget():
    import time

    deadline = time.monotonic() + 2.5
    remaining = remaining_timeout_ms(deadline)

    assert 2000 <= remaining <= 2500


def test_ready_status_must_hide_after_ready_log():
    class FakeTimeoutError(Exception):
        pass

    class StuckPage:
        selector: str | None = None
        timeout: int | None = None
        state: str | None = None

        def wait_for_selector(
            self, selector: str, *, timeout: int, state: str = "visible"
        ) -> None:
            self.selector = selector
            self.timeout = timeout
            self.state = state
            raise FakeTimeoutError("timed out")

    page = StuckPage()

    with pytest.raises(RuntimeError, match="did not hide the loading UI"):
        assert_ready_status_hidden(
            page,
            timeout_ms=0,
            timeout_error=FakeTimeoutError,
        )

    assert page.selector == '#pygodide-loader[data-state="hidden"]'
    assert page.state == "attached"
    assert page.timeout == 1


def test_load_target_manifest_reads_expected_warning_hang_config(tmp_path):
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / MANIFEST_FILENAME).write_text(
        """
name: hang-target
smoke:
  expected-warning: "[pygodide] async hang"
  post-ready-ms: 2000
  timeout-ms: 60000
""".strip(),
        encoding="utf-8",
    )

    manifest = load_target_manifest(target_dir)

    assert manifest.smoke.expected_warning == "[pygodide] async hang"
    assert manifest.smoke.expect_ready is False
    assert manifest.smoke.post_ready_ms == 2000
    assert manifest.smoke.timeout_ms == 60000


def test_load_target_manifest_allows_expected_warning_with_ready(tmp_path):
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / MANIFEST_FILENAME).write_text(
        """
name: warn-and-ready
smoke:
  expected-warning: "something odd"
  expect-ready: true
""".strip(),
        encoding="utf-8",
    )

    manifest = load_target_manifest(target_dir)

    assert manifest.smoke.expected_warning == "something odd"
    assert manifest.smoke.expect_ready is True


def test_resolve_smoke_config_keeps_manifest_hang_fields(tmp_path):
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / MANIFEST_FILENAME).write_text(
        """
name: hang-target
smoke:
  expected-warning: "[pygodide] async hang"
  timeout-ms: 60000
""".strip(),
        encoding="utf-8",
    )

    config = resolve_smoke_config(target_dir)

    assert config.expected_warning == "[pygodide] async hang"
    assert config.expect_ready is False
    assert config.timeout_ms == 60000


def test_evaluate_smoke_result_accepts_expected_hang_warning():
    smoke = SmokeConfig(
        expected_warning="[pygodide] async hang",
        expect_ready=False,
    )
    evaluate_smoke_result(
        smoke,
        SmokeObservation(expected_warning_seen=True, ready_seen=False),
    )


def test_evaluate_smoke_result_rejects_ready_when_hang_expected():
    smoke = SmokeConfig(
        expected_warning="[pygodide] async hang",
        expect_ready=False,
    )
    with pytest.raises(RuntimeError, match="became ready"):
        evaluate_smoke_result(
            smoke,
            SmokeObservation(expected_warning_seen=True, ready_seen=True),
        )


def test_evaluate_smoke_result_rejects_missing_expected_warning():
    smoke = SmokeConfig(
        expected_warning="[pygodide] async hang",
        expect_ready=False,
        timeout_ms=12_000,
    )
    with pytest.raises(RuntimeError, match="expected warning"):
        evaluate_smoke_result(
            smoke,
            SmokeObservation(expected_warning_seen=False, ready_seen=False),
        )


def test_evaluate_smoke_result_still_requires_ready_for_normal_targets():
    smoke = SmokeConfig()
    with pytest.raises(RuntimeError, match="ready log"):
        evaluate_smoke_result(
            smoke,
            SmokeObservation(ready_seen=False),
        )


def test_evaluate_smoke_result_surfaces_console_failures():
    smoke = SmokeConfig(expected_warning="[pygodide] async hang", expect_ready=False)
    with pytest.raises(RuntimeError, match="console error"):
        evaluate_smoke_result(
            smoke,
            SmokeObservation(
                expected_warning_seen=True,
                failures=("console error: boom",),
            ),
        )


def test_startup_python_arms_yield_watchdog_before_entrypoint():
    startup = build_startup_python_code(
        entry_module="main",
        entry_function="main",
        python_path_entries=["/"],
    )

    assert "pygodideWatchdogArm" in startup
    assert "pygodideHeartbeat" in startup
    assert "pygodideWatchdogDisarm" in startup
    assert "_pygodide_heartbeat_loop" in startup
    assert "create_task" in startup
    assert "_pygodide_ready_on_first_yield" in startup
    # Arm parent-shell watchdog before the game task runs; disarm only after.
    assert startup.index("pygodideWatchdogArm()") < startup.index("create_task(main())")
    assert startup.index("create_task(main())") < startup.index(
        "pygodideWatchdogDisarm()"
    )


def test_async_hang_fixture_manifest_is_discoverable():
    repo_targets = Path(__file__).resolve().parents[1] / "test_targets"
    targets = discover_targets(repo_targets, target_names=["async-hang"])
    assert len(targets) == 1
    manifest = targets[0].manifest
    assert manifest.auto_async is False
    assert manifest.smoke.expected_warning == "[pygodide] async hang"
    assert manifest.smoke.expected_warning.startswith(
        ASYNC_HANG_WARNING_PREFIX.rstrip(":")
    )
    assert manifest.smoke.expect_ready is False
    main_py = (targets[0].path / "main.py").read_text(encoding="utf-8")
    assert "async def main" in main_py
    # No real frame yield in the game loop body.
    assert "await " not in "\n".join(
        line
        for line in main_py.splitlines()
        if line.strip() and not line.lstrip().startswith(("#", '"""', "'''"))
    )


def _write_target_manifest(target_dir: Path, name: str) -> Path:
    target_dir.mkdir()
    (target_dir / MANIFEST_FILENAME).write_text(
        f"name: {name}\n",
        encoding="utf-8",
    )
    return target_dir

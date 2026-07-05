from __future__ import annotations

from pathlib import Path

import pytest

from pygodide.compatibility import (
    MANIFEST_FILENAME,
    DiscoveredTarget,
    SmokeConfig,
    TargetManifest,
    _assert_ready_status_hidden,
    _remaining_timeout_ms,
    discover_targets,
    load_target_manifest,
    resolve_smoke_config,
    run_compatibility_suite,
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


def test_run_compatibility_suite_uses_injected_build_and_smoke_runners(tmp_path):
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

    results = run_compatibility_suite(
        tmp_path,
        build_runner=build_runner,
        smoke_runner=smoke_runner,
    )

    assert [result.success for result in results] == [True]
    assert calls == [("build", "demo-target"), ("smoke", "demo-target")]


def test_run_compatibility_suite_reports_target_failures(tmp_path):
    _write_target_manifest(tmp_path / "demo", "demo-target")

    def build_runner(target: DiscoveredTarget) -> Path:
        raise RuntimeError(f"{target.manifest.name} build failed")

    results = run_compatibility_suite(tmp_path, build_runner=build_runner)

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
    remaining = _remaining_timeout_ms(deadline)

    assert 2000 <= remaining <= 2500


def test_ready_status_must_hide_after_ready_log():
    class FakeTimeoutError(Exception):
        pass

    class StuckPage:
        selector: str | None = None
        timeout: int | None = None

        def wait_for_selector(self, selector: str, *, timeout: int) -> None:
            self.selector = selector
            self.timeout = timeout
            raise FakeTimeoutError("timed out")

    page = StuckPage()

    with pytest.raises(RuntimeError, match="did not hide the loading status"):
        _assert_ready_status_hidden(
            page,
            timeout_ms=0,
            timeout_error=FakeTimeoutError,
        )

    assert page.selector == '#status[data-state="hidden"]'
    assert page.timeout == 1


def _write_target_manifest(target_dir: Path, name: str) -> Path:
    target_dir.mkdir()
    (target_dir / MANIFEST_FILENAME).write_text(
        f"name: {name}\n",
        encoding="utf-8",
    )
    return target_dir

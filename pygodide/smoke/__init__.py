"""Smoke testing, target manifests, and Playwright verification."""

from pygodide.smoke.manifest import (
    MANIFEST_FILENAME,
    DiscoveredTarget,
    SmokeConfig,
    SmokeObservation,
    SmokeSuiteResult,
    TargetManifest,
    discover_targets,
    load_target_manifest,
    resolve_smoke_config,
)
from pygodide.smoke.playwright_smoke import (
    assert_ready_status_hidden,
    evaluate_smoke_result,
    remaining_timeout_ms,
    run_playwright_smoke,
)
from pygodide.smoke.runner import (
    build_target,
    run_smoke_suite,
    smoke_test_app,
    smoke_test_target,
)

__all__ = [
    "DiscoveredTarget",
    "MANIFEST_FILENAME",
    "SmokeConfig",
    "SmokeObservation",
    "SmokeSuiteResult",
    "TargetManifest",
    "assert_ready_status_hidden",
    "build_target",
    "discover_targets",
    "evaluate_smoke_result",
    "load_target_manifest",
    "remaining_timeout_ms",
    "resolve_smoke_config",
    "run_playwright_smoke",
    "run_smoke_suite",
    "smoke_test_app",
    "smoke_test_target",
]

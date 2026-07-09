"""Smoke testing, target manifests, and Playwright verification."""

from pygodide.smoke.manifest import (
    MANIFEST_FILENAME,
    discover_targets,
    load_target_manifest,
    resolve_smoke_config,
)
from pygodide.smoke.playwright_smoke import (
    assert_ready_status_hidden,
    remaining_timeout_ms,
    run_playwright_smoke,
)
from pygodide.smoke.runner import (
    build_target,
    run_smoke_suite,
    smoke_test_app,
    smoke_test_target,
)
from pygodide.smoke.types import (
    DiscoveredTarget,
    SmokeConfig,
    SmokeSuiteResult,
    TargetManifest,
)

__all__ = [
    "DiscoveredTarget",
    "MANIFEST_FILENAME",
    "SmokeConfig",
    "SmokeSuiteResult",
    "TargetManifest",
    "assert_ready_status_hidden",
    "build_target",
    "discover_targets",
    "load_target_manifest",
    "remaining_timeout_ms",
    "resolve_smoke_config",
    "run_playwright_smoke",
    "run_smoke_suite",
    "smoke_test_app",
    "smoke_test_target",
]

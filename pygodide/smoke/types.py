from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pygodide.rendering import DEFAULT_READY_LOG

DEFAULT_SMOKE_PATH = "/"
DEFAULT_TIMEOUT_MS = 120_000
DEFAULT_POST_READY_MS = 500
# Loader is visibility:hidden when dismissed, so smoke waits for "attached",
# not "visible". Status lives inside the loader overlay.
READY_STATUS_SELECTOR = '#pygodide-loader[data-state="hidden"]'


@dataclass(frozen=True)
class SmokeConfig:
    path: str = DEFAULT_SMOKE_PATH
    ready_log: str = DEFAULT_READY_LOG
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    post_ready_ms: int = DEFAULT_POST_READY_MS
    # When set, smoke treats a console/page message containing this substring as
    # the success signal (e.g. hang-watchdog guidance). Combined with
    # expect_ready=False for fixtures that must not become ready.
    expected_warning: str | None = None
    expect_ready: bool = True


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
class SmokeSuiteResult:
    target_name: str
    target_path: Path
    build_dir: Path | None
    success: bool
    error: str | None = None


@dataclass(frozen=True)
class SmokeObservation:
    """Browser observations collected during a smoke run (pure decision input)."""

    ready_seen: bool = False
    expected_warning_seen: bool = False
    failures: tuple[str, ...] = ()
    timed_out: bool = False


BuildRunner = Callable[[DiscoveredTarget], Path]
SmokeRunner = Callable[[DiscoveredTarget, Path], None]
Echo = Callable[[str], None]

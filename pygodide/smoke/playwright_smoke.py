from __future__ import annotations

import threading
import time
from typing import Any

from pygodide.smoke.types import (
    READY_STATUS_SELECTOR,
    SmokeConfig,
    SmokeObservation,
)

# hideLoadingUi fades ~180ms; give slow CI enough budget after a late ready.
MIN_LOADER_HIDE_MS = 2_000
# GitHub Actions (and other small /dev/shm hosts) otherwise flake or hang Chromium.
CHROMIUM_LAUNCH_ARGS = ("--disable-dev-shm-usage",)


def evaluate_smoke_result(smoke: SmokeConfig, observation: SmokeObservation) -> None:
    """Raise RuntimeError when a smoke observation does not satisfy config.

    Pure decision helper so unit tests can cover expected-hang acceptance without
    launching a browser.
    """
    if observation.failures:
        raise RuntimeError("; ".join(observation.failures))

    status_hint = ""
    if observation.last_status:
        status_hint = f" Last page status: {observation.last_status!r}."

    if smoke.expected_warning:
        if not observation.expected_warning_seen:
            raise RuntimeError(
                f"Timed out waiting for expected warning "
                f"{smoke.expected_warning!r} after {smoke.timeout_ms} ms."
                f"{status_hint}"
            )
        if smoke.expect_ready:
            if not observation.ready_seen:
                raise RuntimeError(
                    f"Timed out waiting for ready log {smoke.ready_log!r} "
                    f"after {smoke.timeout_ms} ms "
                    f"(expected warning was observed).{status_hint}"
                )
        elif observation.ready_seen:
            raise RuntimeError(
                "Expected hang/stuck behavior "
                f"(warning {smoke.expected_warning!r}) but the app became ready"
            )
        return

    if not observation.ready_seen:
        raise RuntimeError(
            f"Timed out waiting for ready log {smoke.ready_log!r} "
            f"after {smoke.timeout_ms} ms.{status_hint}"
        )


def run_playwright_smoke(smoke: SmokeConfig, base_url: str) -> None:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Playwright is not installed. Install the smoke extra and Chromium "
            "with: pip install 'pygodide[smoke]' && playwright install chromium "
            "(or from this repo: uv sync --dev && "
            "uv run playwright install chromium)."
        ) from exc

    ready_seen = threading.Event()
    expected_warning_seen = threading.Event()
    failures: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=list(CHROMIUM_LAUNCH_ARGS))
        page = browser.new_page()

        def handle_console(message) -> None:
            text = message.text
            if text == smoke.ready_log:
                ready_seen.set()
            if smoke.expected_warning and smoke.expected_warning in text:
                expected_warning_seen.set()
            if message.type == "error":
                failures.append(f"console error: {text}")

        page.on("console", handle_console)
        page.on("pageerror", lambda exc: failures.append(f"page error: {exc}"))

        try:
            page.goto(join_url(base_url, smoke.path), wait_until="domcontentloaded")
            deadline = time.monotonic() + smoke.timeout_ms / 1000
            observation = _collect_playwright_observation(
                page,
                smoke=smoke,
                ready_seen=ready_seen,
                expected_warning_seen=expected_warning_seen,
                failures=failures,
                deadline=deadline,
                timeout_error=PlaywrightTimeoutError,
            )
        finally:
            browser.close()

    evaluate_smoke_result(smoke, observation)


def _collect_playwright_observation(
    page: Any,
    *,
    smoke: SmokeConfig,
    ready_seen: threading.Event,
    expected_warning_seen: threading.Event,
    failures: list[str],
    deadline: float,
    timeout_error: type[BaseException],
) -> SmokeObservation:
    if smoke.expected_warning and not smoke.expect_ready:
        while (
            not expected_warning_seen.is_set()
            and not failures
            and not ready_seen.is_set()
        ):
            if time.monotonic() >= deadline:
                break
            _poll_expected_warning_from_page(
                page, smoke.expected_warning, expected_warning_seen
            )
            page.wait_for_timeout(100)

        if expected_warning_seen.is_set() and not ready_seen.is_set() and not failures:
            # Confirm the app stays hung (healthy games become ready quickly).
            page.wait_for_timeout(smoke.post_ready_ms)
            _poll_expected_warning_from_page(
                page, smoke.expected_warning, expected_warning_seen
            )

        return SmokeObservation(
            ready_seen=ready_seen.is_set(),
            expected_warning_seen=expected_warning_seen.is_set(),
            failures=tuple(failures),
            timed_out=time.monotonic() >= deadline
            and not expected_warning_seen.is_set(),
            last_status=_page_status_text(page),
        )

    while not ready_seen.is_set() and not failures:
        if smoke.expected_warning:
            _poll_expected_warning_from_page(
                page, smoke.expected_warning, expected_warning_seen
            )
        if time.monotonic() >= deadline:
            break
        page.wait_for_timeout(100)

    if ready_seen.is_set() and not failures:
        try:
            # Ready can arrive near the deadline on cold CI CDN loads; still allow
            # time for the loader fade so we do not mis-report a yield hang.
            hide_timeout_ms = max(
                remaining_timeout_ms(deadline),
                MIN_LOADER_HIDE_MS,
            )
            assert_ready_status_hidden(
                page,
                timeout_ms=hide_timeout_ms,
                timeout_error=timeout_error,
            )
        except RuntimeError as exc:
            failures.append(str(exc))
        else:
            page.wait_for_timeout(smoke.post_ready_ms)

    return SmokeObservation(
        ready_seen=ready_seen.is_set(),
        expected_warning_seen=expected_warning_seen.is_set(),
        failures=tuple(failures),
        timed_out=time.monotonic() >= deadline and not ready_seen.is_set(),
        last_status=_page_status_text(page),
    )


def _page_status_text(page: Any) -> str | None:
    try:
        text = page.locator("#status").inner_text(timeout=200)
    except Exception:
        return None
    text = (text or "").strip()
    return text or None


def _poll_expected_warning_from_page(
    page: Any, expected_warning: str, expected_warning_seen: threading.Event
) -> None:
    """Also match hang text painted into #status (console may be enough alone)."""
    if expected_warning_seen.is_set():
        return
    try:
        status_text = page.locator("#status").inner_text(timeout=100)
    except Exception:
        return
    if expected_warning in (status_text or ""):
        expected_warning_seen.set()


def remaining_timeout_ms(deadline: float) -> int:
    return max(1, int((deadline - time.monotonic()) * 1000))


def assert_ready_status_hidden(
    page: Any,
    *,
    timeout_ms: int,
    timeout_error: type[BaseException],
) -> None:
    try:
        # state="attached": the loader uses visibility:hidden when dismissed, so
        # Playwright's default "visible" check would never match.
        page.wait_for_selector(
            READY_STATUS_SELECTOR,
            state="attached",
            timeout=max(timeout_ms, 1),
        )
    except timeout_error as exc:
        raise RuntimeError(
            "Page logged ready but did not hide the loading UI. "
            "The app may be blocking the browser event loop; make the entrypoint "
            "async and yield with await asyncio.sleep(1 / (fps * 2)) "
            "in long-running loops."
        ) from exc


def join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

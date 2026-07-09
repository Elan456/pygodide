from __future__ import annotations

import threading
import time
from typing import Any

from pygodide.smoke.types import READY_STATUS_SELECTOR, SmokeConfig


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
            page.goto(join_url(base_url, smoke.path), wait_until="domcontentloaded")
            deadline = time.monotonic() + smoke.timeout_ms / 1000
            while not ready_seen.is_set() and not failures:
                if time.monotonic() >= deadline:
                    break
                page.wait_for_timeout(100)

            if ready_seen.is_set() and not failures:
                try:
                    assert_ready_status_hidden(
                        page,
                        timeout_ms=remaining_timeout_ms(deadline),
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


def remaining_timeout_ms(deadline: float) -> int:
    return max(1, int((deadline - time.monotonic()) * 1000))


def assert_ready_status_hidden(
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


def join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

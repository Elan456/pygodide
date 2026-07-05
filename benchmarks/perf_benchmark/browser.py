from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from perf_benchmark.browser_launch import BrowserSettings, ensure_display_available
from perf_benchmark.config import (
    BENCHMARK_TIMEOUT_S,
    PYGBAG_BUILD_ARGS,
    REPO_ROOT,
)
from perf_benchmark.models import BenchmarkResult
from perf_benchmark.parse import parse_benchmark_done
from perf_benchmark.serve import serve_directory
from perf_benchmark.workspace import prepare_work_copy

LogFn = Callable[[str], None]


def _default_log(message: str) -> None:
    print(message)


def _ensure_playwright() -> None:
    try:
        import playwright  # noqa: F401
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Playwright is not installed. From benchmarks/, run:\n"
            "  uv sync\n"
            "  uv run playwright install chromium"
        ) from exc


def _run_repo_command(args: list[str], *, log: LogFn) -> None:
    log(f"Running: uv run {' '.join(args)}")
    completed = subprocess.run(
        ["uv", "run", *args],
        cwd=REPO_ROOT,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): uv run {' '.join(args)}"
        )


def _collect_pygodide_result(
    build_dir: Path,
    *,
    browser: BrowserSettings,
    timeout_s: float,
    log: LogFn,
) -> tuple[BenchmarkResult, str | None]:
    from playwright.sync_api import sync_playwright

    console_lines: list[str] = []
    page_errors: list[str] = []
    started = time.monotonic()
    browser_version: str | None = None

    with serve_directory(build_dir) as base_url:
        with sync_playwright() as playwright:
            browser = browser.launch(playwright)
            browser_version = browser.version
            page = browser.new_page()

            def handle_console(message) -> None:
                console_lines.append(message.text)
                if message.type == "error":
                    page_errors.append(message.text)

            page.on("console", handle_console)
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))

            page.goto(f"{base_url}/", wait_until="domcontentloaded", timeout=60_000)

            deadline = time.monotonic() + timeout_s
            parsed: tuple[float, int] | None = None
            while time.monotonic() < deadline:
                for line in console_lines:
                    parsed = parse_benchmark_done(line)
                    if parsed is not None:
                        break
                if parsed is not None:
                    break
                page.wait_for_timeout(250)

            browser.close()

    duration_s = time.monotonic() - started
    if parsed is not None:
        fps_mean, samples = parsed
        return (
            BenchmarkResult(
                runtime="pygodide",
                fps_mean=fps_mean,
                samples=samples,
                status="ok",
                duration_s=duration_s,
            ),
            browser_version,
        )

    error_parts = page_errors or console_lines[-10:]
    return (
        BenchmarkResult(
            runtime="pygodide",
            fps_mean=None,
            samples=None,
            status="timeout" if not page_errors else "error",
            duration_s=duration_s,
            error="; ".join(error_parts)
            if error_parts
            else f"Timed out after {timeout_s:.0f}s",
        ),
        browser_version,
    )


def _collect_pygbag_result(
    build_dir: Path,
    *,
    browser: BrowserSettings,
    timeout_s: float,
    log: LogFn,
) -> tuple[BenchmarkResult, str | None]:
    from playwright.sync_api import sync_playwright

    console_lines: list[str] = []
    page_errors: list[str] = []
    started = time.monotonic()
    browser_version: str | None = None

    with serve_directory(build_dir) as base_url:
        with sync_playwright() as playwright:
            browser = browser.launch(playwright)
            browser_version = browser.version
            page = browser.new_page()

            def handle_console(message) -> None:
                console_lines.append(message.text)
                if message.type == "error":
                    page_errors.append(message.text)

            page.on("console", handle_console)
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))

            page.goto(
                f"{base_url}/index.html",
                wait_until="load",
                timeout=60_000,
            )

            deadline = time.monotonic() + timeout_s
            parsed: tuple[float, int] | None = None
            while time.monotonic() < deadline:
                terminal_text = page.evaluate(
                    """() => {
                        const rows = document.querySelector('.xterm-rows');
                        return rows ? rows.innerText : '';
                    }"""
                )
                for blob in (terminal_text, "\n".join(console_lines)):
                    parsed = parse_benchmark_done(blob)
                    if parsed is not None:
                        break
                if parsed is not None:
                    break
                page.wait_for_timeout(250)

            browser.close()

    duration_s = time.monotonic() - started
    if parsed is not None:
        fps_mean, samples = parsed
        return (
            BenchmarkResult(
                runtime="pygbag",
                fps_mean=fps_mean,
                samples=samples,
                status="ok",
                duration_s=duration_s,
            ),
            browser_version,
        )

    error_parts = page_errors or console_lines[-10:]
    return (
        BenchmarkResult(
            runtime="pygbag",
            fps_mean=None,
            samples=None,
            status="timeout" if not page_errors else "error",
            duration_s=duration_s,
            error="; ".join(error_parts)
            if error_parts
            else f"Timed out after {timeout_s:.0f}s",
        ),
        browser_version,
    )


def run_pygodide_benchmark(
    *,
    browser: BrowserSettings | None = None,
    timeout_s: float = BENCHMARK_TIMEOUT_S,
    log: LogFn = _default_log,
) -> tuple[BenchmarkResult, str | None]:
    _ensure_playwright()
    settings = browser or BrowserSettings()
    if not settings.headless:
        ensure_display_available()
    work_dir = prepare_work_copy("pygodide")
    _run_repo_command(["pygodide", "build", str(work_dir)], log=log)
    return _collect_pygodide_result(
        work_dir / "build",
        browser=settings,
        timeout_s=timeout_s,
        log=log,
    )


def run_pygbag_benchmark(
    *,
    browser: BrowserSettings | None = None,
    timeout_s: float = BENCHMARK_TIMEOUT_S,
    log: LogFn = _default_log,
) -> tuple[BenchmarkResult, str | None]:
    _ensure_playwright()
    settings = browser or BrowserSettings()
    if not settings.headless:
        ensure_display_available()
    work_dir = prepare_work_copy("pygbag")
    _run_repo_command(["pygbag", *PYGBAG_BUILD_ARGS, str(work_dir)], log=log)
    return _collect_pygbag_result(
        work_dir / "build" / "web",
        browser=settings,
        timeout_s=timeout_s,
        log=log,
    )

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from perf_benchmark.browser import run_pygbag_benchmark, run_pygodide_benchmark
from perf_benchmark.browser_launch import BrowserEngine, BrowserSettings
from perf_benchmark.chart import load_report, write_chart, write_json_report
from perf_benchmark.config import (
    BENCHMARK_TIMEOUT_S,
    DEFAULT_CHART_HTML,
    DEFAULT_RESULTS_JSON,
    DOCS_CHART_HTML,
    LOCAL_TIMEOUT_S,
    README_CHART_PNG,
    SCENARIO_NAME,
)
from perf_benchmark.local import run_local_benchmark
from perf_benchmark.metadata import collect_environment
from perf_benchmark.models import BenchmarkReport, BenchmarkResult


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run perf_bench across local pygame, pygodide, and pygbag; "
            "save JSON results and a Plotly bar chart."
        )
    )
    parser.add_argument(
        "--results-json",
        type=Path,
        default=DEFAULT_RESULTS_JSON,
        help=f"Where to write JSON results (default: {DEFAULT_RESULTS_JSON})",
    )
    parser.add_argument(
        "--chart-html",
        type=Path,
        default=DEFAULT_CHART_HTML,
        help=f"Where to write the chart HTML (default: {DEFAULT_CHART_HTML})",
    )
    parser.add_argument(
        "--chart-only",
        action="store_true",
        help="Regenerate the chart from an existing results JSON file",
    )
    parser.add_argument("--skip-local", action="store_true")
    parser.add_argument("--skip-pygodide", action="store_true")
    parser.add_argument("--skip-pygbag", action="store_true")
    parser.add_argument(
        "--browser-timeout",
        type=float,
        default=BENCHMARK_TIMEOUT_S,
        help="Seconds to wait for browser benchmark completion",
    )
    parser.add_argument(
        "--local-timeout",
        type=float,
        default=LOCAL_TIMEOUT_S,
        help="Seconds to wait for the local benchmark process",
    )
    parser.add_argument(
        "--browser",
        choices=("chromium", "firefox"),
        default="chromium",
        help="Playwright browser engine for pygodide (default: chromium)",
    )
    parser.add_argument(
        "--pygbag-browser",
        choices=("chromium", "firefox"),
        default=None,
        help="Playwright browser for pygbag (default: same as --browser)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help=(
            "Run browser benchmarks without a visible window. "
            "Headless Chromium can report much higher FPS than a real browser tab."
        ),
    )
    parser.add_argument(
        "--uncap-framerate",
        action="store_true",
        help=(
            "Disable Chromium frame-rate limits. Only useful with --headless; "
            "headed runs use normal browser pacing by default."
        ),
    )
    return parser.parse_args()


def _browser_settings(
    engine: BrowserEngine,
    *,
    headless: bool,
    uncap_framerate: bool,
) -> BrowserSettings:
    return BrowserSettings(
        engine=engine,
        headless=headless,
        uncap_framerate=uncap_framerate,
    )


def _print_result(result: BenchmarkResult) -> None:
    if result.status == "ok" and result.fps_mean is not None:
        print(
            f"[{result.runtime}] fps_mean={result.fps_mean:.2f} "
            f"samples={result.samples} ({result.duration_s:.1f}s)"
        )
        return
    print(f"[{result.runtime}] {result.status}: {result.error}")


def _load_existing_results(path: Path) -> dict[str, BenchmarkResult]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        name: BenchmarkResult(**result) for name, result in payload["results"].items()
    }


def main() -> int:
    args = _parse_args()

    if args.chart_only:
        if not args.results_json.is_file():
            print(f"Results file not found: {args.results_json}", file=sys.stderr)
            return 1
        report = load_report(args.results_json)
        chart_path = write_chart(report, args.chart_html)
        print(f"Wrote chart: {chart_path}")
        print(f"Wrote docs chart: {DOCS_CHART_HTML}")
        print(f"Wrote README chart: {README_CHART_PNG}")
        return 0

    results: dict[str, BenchmarkResult] = {}
    browser_version: str | None = None
    pygodide_browser = _browser_settings(
        args.browser,
        headless=args.headless,
        uncap_framerate=args.uncap_framerate,
    )
    pygbag_browser = _browser_settings(
        args.pygbag_browser or args.browser,
        headless=args.headless,
        uncap_framerate=args.uncap_framerate,
    )
    browser_settings_report = {
        "pygodide": pygodide_browser.describe(),
        "pygbag": pygbag_browser.describe(),
    }

    if not args.skip_local:
        print("Running local benchmark...")
        results["local"] = run_local_benchmark(timeout_s=args.local_timeout)
        _print_result(results["local"])

    if not args.skip_pygodide:
        print("Running pygodide benchmark...")
        pygodide_result, browser_version = run_pygodide_benchmark(
            browser=pygodide_browser,
            timeout_s=args.browser_timeout,
        )
        results["pygodide"] = pygodide_result
        _print_result(pygodide_result)

    if not args.skip_pygbag:
        print("Running pygbag benchmark...")
        pygbag_result, pygbag_browser_version = run_pygbag_benchmark(
            browser=pygbag_browser,
            timeout_s=args.browser_timeout,
        )
        results["pygbag"] = pygbag_result
        browser_version = browser_version or pygbag_browser_version
        _print_result(pygbag_result)

    environment = collect_environment(
        browser_version=browser_version,
        browser_settings=browser_settings_report,
    )
    report = BenchmarkReport(
        scenario=SCENARIO_NAME,
        generated_at=datetime.now(UTC).isoformat(),
        environment=environment,
        results=results,
    )

    json_path = write_json_report(report, args.results_json)
    chart_path = write_chart(report, args.chart_html)

    print(f"Wrote results: {json_path}")
    print(f"Wrote chart: {chart_path}")
    print(f"Wrote docs chart: {DOCS_CHART_HTML}")
    print(f"Wrote README chart: {README_CHART_PNG}")

    failed = [name for name, result in results.items() if result.status != "ok"]
    if failed:
        print(
            f"Benchmark completed with failures: {', '.join(failed)}", file=sys.stderr
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

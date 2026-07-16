from __future__ import annotations

from pathlib import Path

BENCHMARKS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BENCHMARKS_ROOT.parent
TARGET_SOURCE = REPO_ROOT / "test_targets" / "perf_bench"
WORK_ROOT = BENCHMARKS_ROOT / ".work"
RESULTS_DIR = BENCHMARKS_ROOT / "results"
OUTPUT_DIR = BENCHMARKS_ROOT / "output"

DEFAULT_RESULTS_JSON = RESULTS_DIR / "latest.json"
DEFAULT_CHART_HTML = OUTPUT_DIR / "benchmark-chart.html"
DOCS_CHART_HTML = REPO_ROOT / "docs" / "assets" / "benchmark-chart.html"
# Compact Plotly export (pygodide vs pygbag only) for GitHub README embeds.
README_CHART_PNG = REPO_ROOT / "docs" / "assets" / "images" / "benchmark-readme.png"
OUTPUT_README_CHART_PNG = OUTPUT_DIR / "benchmark-readme.png"

SCENARIO_NAME = "perf_bench"
BENCHMARK_READY_LOG = "[benchmark] ready"
BENCHMARK_TIMEOUT_S = 120.0
LOCAL_TIMEOUT_S = 90.0

PYGODIDE_CANVAS = (800, 600)
PYGBAG_BUILD_ARGS = (
    "--build",
    "--width",
    "800",
    "--height",
    "600",
    "--ume_block",
    "0",
)

# Cross-runtime FPS benchmarks

Standalone harness that runs [`test_targets/perf_bench`](../test_targets/perf_bench)
on three runtimes and writes reproducible JSON results plus a Plotly bar chart.

| Runtime | How it is measured |
| --- | --- |
| **Local** | Native `pygame-ce`; parses `[benchmark] done ...` from stdout |
| **pygodide** | `pygodide build` + headed Chromium window; parses browser console |
| **pygbag** | `pygbag --build` + headed Chromium window; parses pygbag xterm output |

This harness is intentionally **not** part of the `pygodide` CLI. Install its
dependencies via the repository dev group (`plotly`, `pygbag`, and Playwright
through `pygodide[smoke]`).

## Prerequisites

From the **repository root**:

```bash
uv sync --dev
uv run playwright install chromium
# optional, only if you pass --pygbag-browser firefox
uv run playwright install firefox
```

You need a working display (or remote X/Wayland session) for **all** benchmarks:
local pygame and the default headed browser runs.

## Run the full suite

```bash
uv run python benchmarks/run.py
```

A real browser window opens for each web runtime, similar to testing manually.

Outputs:

- `benchmarks/results/latest.json`: machine metadata + FPS means
- `benchmarks/output/benchmark-chart.html`: interactive Plotly chart (local + pygodide + pygbag)
- `docs/assets/benchmark-chart.html`: same full chart for the docs site
- `docs/assets/images/benchmark-readme.png`: compact Plotly chart (pygodide vs pygbag) for the GitHub README

The full run takes roughly 2-4 minutes (5s warmup + 20s measurement per runtime,
plus build/load overhead).

## Useful options

```bash
# Skip runtimes you cannot run on this machine
uv run python benchmarks/run.py --skip-local
uv run python benchmarks/run.py --skip-pygbag

# Measure pygbag in Firefox (after: uv run playwright install firefox)
uv run python benchmarks/run.py --pygbag-browser firefox

# Headless automation (faster, but FPS can be much higher than a real tab)
uv run python benchmarks/run.py --headless

# Headless without Chromium's 60 Hz rAF cap (even less realistic)
uv run python benchmarks/run.py --headless --uncap-framerate

# Regenerate the chart from saved JSON
uv run python benchmarks/run.py --chart-only

# Custom output paths
uv run python benchmarks/run.py \
  --results-json benchmarks/results/my-run.json \
  --chart-html benchmarks/output/my-chart.html
```

## Why headed by default

Headless Playwright Chromium often reports **much higher FPS** than you see in a
normal browser tab (for example ~500 vs ~215 on the same machine). The harness
defaults to a **visible browser window** with normal frame pacing so browser
numbers are closer to manual testing.

Use `--headless` only for CI or quick smoke checks. Avoid `--uncap-framerate`
unless you explicitly want synthetic uncapped headless numbers.

Headed runs prefer an installed **Google Chrome** (`channel="chrome"`) when
available, falling back to Playwright's bundled Chromium. Numbers should be
checked against your own manual `pygodide serve` / `pygbag` session in the
same browser you care about.

## Protocol

The target app prints lines like:

```text
[benchmark] ready
[benchmark] done fps_mean=215.00 samples=1200
```

The harness waits for the `done` line. See
[`docs/benchmark-proposal.md`](../docs/benchmark-proposal.md) for methodology notes.

## Reproducibility notes

- Results vary by CPU, GPU, browser build, monitor refresh rate, and thermal state.
- Default browser runs are **headed Chromium** with normal pacing.
- pygbag builds use `--ume_block 0` so no click is required in automation.
- Each runtime builds from a fresh copy under `benchmarks/.work/` so outputs do
  not overwrite `test_targets/perf_bench/build/`.
- Pin tool versions via the repository `uv.lock` (`uv sync --dev` at repo root).
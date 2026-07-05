# Performance benchmarks

Cross-runtime FPS comparison for the [`perf_bench`](../test_targets/perf_bench)
workload — a small async Pygame game used to measure sustained frame rate on
**local desktop**, **pygodide**, and **pygbag**.

<div class="benchmark-chart-frame" markdown="0">
<iframe
  src="assets/benchmark-chart.html"
  title="FPS benchmark"
  loading="lazy"
></iframe>
</div>

## Latest results

_Generated: 2026-07-05T22:48:07Z_

| Runtime | Mean FPS | Samples | Duration |
| --- | ---: | ---: | ---: |
| Local | 950.46 | 18,787 | 25.5 s |
| pygodide | 432.65 | 8,584 | 28.5 s |
| pygbag | 180.03 | 3,601 | 28.8 s |

Higher is better. Each web runtime uses a **headed browser window** (not headless
automation) so numbers are closer to manual testing.

### Environment

| Field | Value |
| --- | --- |
| Scenario | `perf_bench` |
| Platform | Linux 7.1.2-3-cachyos (x86_64) |
| Python | 3.12.13 (CPython) |
| pygame-ce | 2.5.7 (SDL 2.32.10) |
| pygodide | 0.1.0b5 |
| pygbag | 0.9.3 |
| Browser | Chromium 150.0.7871.46 (headed, system Chrome when available) |
| Playwright | 1.60.0 |
| Plotly | 6.8.0 |

### Browser settings

Both pygodide and pygbag benchmarks used:

- Engine: Chromium (headed)
- Frame-rate uncap: disabled (normal browser pacing)
- Launch args: `--disable-background-timer-throttling`,
  `--disable-backgrounding-occluded-windows`,
  `--disable-renderer-backgrounding`

Raw JSON: [`benchmarks/results/latest.json`](../benchmarks/results/latest.json)

## Reproduce locally

From the repository root:

```bash
uv sync --dev
uv run playwright install chromium
uv run python benchmarks/run.py
```

This opens a real browser window for each web runtime, runs the benchmark game
for 5 seconds of warmup plus 20 seconds of measurement, and writes:

- `benchmarks/results/latest.json`
- `benchmarks/output/benchmark-chart.html`
- `docs/assets/benchmark-chart.html` (copied for the docs site)

Regenerate only the chart from saved JSON:

```bash
uv run python benchmarks/run.py --chart-only
```

### Useful options

```bash
# Skip runtimes you cannot run on this machine
uv run python benchmarks/run.py --skip-local
uv run python benchmarks/run.py --skip-pygbag

# Measure pygbag in Firefox (after: uv run playwright install firefox)
uv run python benchmarks/run.py --pygbag-browser firefox

# Headless automation (faster, but often unrealistic FPS)
uv run python benchmarks/run.py --headless
```

You need a graphical session for the default headed runs (same as local pygame).

## Methodology

The benchmark app logs:

```text
[benchmark] ready
[benchmark] done fps_mean=432.65 samples=8584
```

| Runtime | How FPS is collected |
| --- | --- |
| **Local** | Parse stdout from native `pygame-ce` |
| **pygodide** | Parse browser console after `pygodide build` |
| **pygbag** | Parse pygbag xterm output after `pygbag --build` |

See [benchmark proposal](benchmark-proposal.md) for design notes and caveats.

!!! note "Results vary by machine"
    CPU, GPU, browser build, and monitor refresh rate all affect FPS. Treat
    published numbers as a reference run on one machine, not a guarantee on
    yours. Re-run the harness to compare on your hardware.
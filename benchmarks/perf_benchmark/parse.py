from __future__ import annotations

import re

BENCHMARK_DONE_RE = re.compile(r"\[benchmark\] done fps_mean=([\d.]+) samples=(\d+)")


def parse_benchmark_done(text: str) -> tuple[float, int] | None:
    match = BENCHMARK_DONE_RE.search(text)
    if match is None:
        return None
    return float(match.group(1)), int(match.group(2))

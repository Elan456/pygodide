from __future__ import annotations

import time

WARMUP_SECONDS = 5.0
MEASURE_SECONDS = 20.0


class BenchmarkSampler:
    """Collects sustained FPS for the cross-runtime benchmark harness."""

    def __init__(
        self,
        *,
        warmup_seconds: float = WARMUP_SECONDS,
        measure_seconds: float = MEASURE_SECONDS,
    ) -> None:
        self.warmup_seconds = warmup_seconds
        self.measure_seconds = measure_seconds
        self._ready_logged = False
        self._started_at: float | None = None
        self._measure_started_at: float | None = None
        self._samples: list[float] = []
        self._done_logged = False

    @property
    def is_complete(self) -> bool:
        return self._done_logged

    @property
    def phase(self) -> str:
        if not self._ready_logged or self._started_at is None:
            return "boot"
        elapsed = time.monotonic() - self._started_at
        if elapsed < self.warmup_seconds:
            return "warmup"
        if not self._done_logged:
            return "measure"
        return "done"

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    @property
    def fps_mean(self) -> float | None:
        if not self._samples:
            return None
        return sum(self._samples) / len(self._samples)

    @property
    def warmup_elapsed(self) -> float:
        if self._started_at is None:
            return 0.0
        return min(time.monotonic() - self._started_at, self.warmup_seconds)

    @property
    def measure_elapsed(self) -> float:
        if self._measure_started_at is None:
            return 0.0
        return min(time.monotonic() - self._measure_started_at, self.measure_seconds)

    def hud_lines(self) -> list[str]:
        if self.phase == "boot":
            return ["Bench: starting"]

        if self.phase == "warmup":
            return [
                "Bench: warmup",
                f"Elapsed: {self.warmup_elapsed:.1f}s / {self.warmup_seconds:.0f}s",
            ]

        if self.phase == "measure":
            lines = [
                "Bench: measuring",
                f"Elapsed: {self.measure_elapsed:.1f}s / {self.measure_seconds:.0f}s",
                f"Samples: {self.sample_count}",
            ]
            if self.fps_mean is not None:
                lines.append(f"FPS mean: {self.fps_mean:.2f}")
            return lines

        mean = self.fps_mean or 0.0
        return [
            "Bench: done",
            f"FPS mean: {mean:.2f}",
            f"Samples: {self.sample_count}",
        ]

    def on_frame(self, fps: float) -> None:
        now = time.monotonic()

        if not self._ready_logged:
            print("[benchmark] ready")
            self._ready_logged = True
            self._started_at = now
            return

        assert self._started_at is not None
        elapsed = now - self._started_at
        if elapsed < self.warmup_seconds:
            return

        if self._measure_started_at is None:
            self._measure_started_at = now

        assert self._measure_started_at is not None
        measure_elapsed = now - self._measure_started_at
        if measure_elapsed < self.measure_seconds:
            self._samples.append(fps)
            return

        if not self._done_logged:
            mean = sum(self._samples) / len(self._samples) if self._samples else 0.0
            print(f"[benchmark] done fps_mean={mean:.2f} samples={len(self._samples)}")
            self._done_logged = True

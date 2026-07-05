from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class BenchmarkResult:
    runtime: str
    fps_mean: float | None
    samples: int | None
    status: str
    duration_s: float | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BenchmarkReport:
    scenario: str
    generated_at: str
    environment: dict[str, Any]
    results: dict[str, BenchmarkResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "generated_at": self.generated_at,
            "environment": self.environment,
            "results": {
                name: result.to_dict() for name, result in self.results.items()
            },
        }

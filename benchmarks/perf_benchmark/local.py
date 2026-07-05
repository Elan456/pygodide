from __future__ import annotations

import subprocess
import time

from perf_benchmark.config import LOCAL_TIMEOUT_S, REPO_ROOT
from perf_benchmark.models import BenchmarkResult
from perf_benchmark.parse import parse_benchmark_done
from perf_benchmark.workspace import prepare_work_copy


def run_local_benchmark(*, timeout_s: float = LOCAL_TIMEOUT_S) -> BenchmarkResult:
    work_dir = prepare_work_copy("local")
    started = time.monotonic()
    output_chunks: list[str] = []

    process = subprocess.Popen(
        [
            "uv",
            "run",
            "--directory",
            str(REPO_ROOT),
            "python",
            "-u",
            str(work_dir / "main.py"),
        ],
        cwd=work_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    parsed: tuple[float, int] | None = None
    deadline = started + timeout_s

    try:
        assert process.stdout is not None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                remaining = process.stdout.read()
                if remaining:
                    output_chunks.append(remaining)
                break

            line = process.stdout.readline()
            if not line:
                time.sleep(0.05)
                continue

            output_chunks.append(line)
            parsed = parse_benchmark_done(line)
            if parsed is not None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
                break
        else:
            process.kill()
            process.wait(timeout=3)
            output = "".join(output_chunks)
            return BenchmarkResult(
                runtime="local",
                fps_mean=None,
                samples=None,
                status="timeout",
                duration_s=time.monotonic() - started,
                error=output[-2000:] or f"Timed out after {timeout_s:.0f}s",
            )
    except Exception as exc:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        output = "".join(output_chunks)
        return BenchmarkResult(
            runtime="local",
            fps_mean=None,
            samples=None,
            status="error",
            duration_s=time.monotonic() - started,
            error=output[-2000:] or str(exc),
        )

    output = "".join(output_chunks)
    duration_s = time.monotonic() - started

    if parsed is None:
        parsed = parse_benchmark_done(output)

    if parsed is None:
        return BenchmarkResult(
            runtime="local",
            fps_mean=None,
            samples=None,
            status="error",
            duration_s=duration_s,
            error=output[-2000:] or f"Process exited with code {process.returncode}",
        )

    fps_mean, samples = parsed
    return BenchmarkResult(
        runtime="local",
        fps_mean=fps_mean,
        samples=samples,
        status="ok",
        duration_s=duration_s,
    )

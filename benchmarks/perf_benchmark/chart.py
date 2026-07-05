from __future__ import annotations

import json
import re
from pathlib import Path

import plotly.graph_objects as go

from perf_benchmark.config import DOCS_CHART_HTML
from perf_benchmark.models import BenchmarkReport

RUNTIME_LABELS = {
    "local": "Local",
    "pygodide": "pygodide",
    "pygbag": "pygbag",
}
RUNTIME_COLORS = {
    "local": "#4C78A8",
    "pygodide": "#F58518",
    "pygbag": "#54A24B",
}
CHART_BG = "#1a1b26"
CHART_HEIGHT = 460
PLOTLY_CONFIG = {"responsive": True, "displayModeBar": False}


def load_report(path: Path) -> BenchmarkReport:
    payload = json.loads(path.read_text(encoding="utf-8"))
    from perf_benchmark.models import BenchmarkResult

    results = {
        name: BenchmarkResult(**result) for name, result in payload["results"].items()
    }
    return BenchmarkReport(
        scenario=payload["scenario"],
        generated_at=payload["generated_at"],
        environment=payload["environment"],
        results=results,
    )


def build_figure(report: BenchmarkReport) -> go.Figure:
    runtimes: list[str] = []
    fps_values: list[float] = []
    colors: list[str] = []
    text_labels: list[str] = []

    for runtime in ("local", "pygodide", "pygbag"):
        result = report.results.get(runtime)
        if result is None or result.fps_mean is None:
            continue
        runtimes.append(RUNTIME_LABELS.get(runtime, runtime))
        fps_values.append(result.fps_mean)
        colors.append(RUNTIME_COLORS.get(runtime, "#888888"))
        sample_text = (
            f"{result.samples} samples" if result.samples is not None else "n/a"
        )
        text_labels.append(f"{result.fps_mean:.1f}<br>{sample_text}")

    figure = go.Figure(
        data=[
            go.Bar(
                x=runtimes,
                y=fps_values,
                marker_color=colors,
                text=text_labels,
                textposition="outside",
                hovertemplate="Runtime=%{x}<br>FPS mean=%{y:.2f}<extra></extra>",
            )
        ]
    )

    env = report.environment
    subtitle_parts = [report.scenario]
    browser_settings = env.get("browser_settings", {})
    pygodide_browser = browser_settings.get("pygodide", {})
    if pygodide_browser.get("headless") is False:
        subtitle_parts.append("headed browser")
    if env.get("browser_version"):
        subtitle_parts.append(f"Chromium {env['browser_version'].split('.')[0]}")
    platform = env.get("platform", "")
    if platform.startswith("Linux"):
        subtitle_parts.append("Linux")
    elif platform.startswith("Windows"):
        subtitle_parts.append("Windows")
    elif platform.startswith("Darwin"):
        subtitle_parts.append("macOS")

    subtitle = " · ".join(subtitle_parts)
    max_fps = max(fps_values) if fps_values else 1.0
    figure.update_layout(
        template="plotly_dark",
        title={
            "text": (
                f"<span style='color:#f1f5f9'>FPS benchmark</span>"
                f"<br><sup style='color:#94a3b8'>{subtitle}</sup>"
            ),
            "font": {"size": 14},
            "x": 0.5,
            "xanchor": "center",
        },
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        font={"color": "#e2e8f0"},
        xaxis_title="Runtime",
        yaxis_title="Mean FPS (higher is better)",
        autosize=True,
        height=CHART_HEIGHT,
        margin=dict(t=58, l=60, r=40, b=60),
    )
    figure.update_yaxes(rangemode="tozero", range=[0, max_fps * 1.12])

    return figure


def _finalize_chart_html(path: Path) -> None:
    html = path.read_text(encoding="utf-8")
    embed_style = (
        "<style>"
        f"html,body{{margin:0;padding:0;background:{CHART_BG};overflow:hidden;}}"
        f"body>div{{width:100%!important;height:{CHART_HEIGHT}px;}}"
        ".plotly-graph-div{height:100%!important;width:100%!important;}"
        "</style>"
    )
    if embed_style not in html:
        html = html.replace("</head>", f"{embed_style}</head>", 1)
    html = re.sub(r"width:\s*\d+px;?", "width:100%;", html)
    path.write_text(html, encoding="utf-8")


def write_chart(report: BenchmarkReport, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure = build_figure(report)
    figure.write_html(
        output_path,
        include_plotlyjs="cdn",
        full_html=True,
        config=PLOTLY_CONFIG,
    )
    _finalize_chart_html(output_path)

    if output_path.resolve() != DOCS_CHART_HTML.resolve():
        DOCS_CHART_HTML.parent.mkdir(parents=True, exist_ok=True)
        figure.write_html(
            DOCS_CHART_HTML,
            include_plotlyjs="cdn",
            full_html=True,
            config=PLOTLY_CONFIG,
        )
        _finalize_chart_html(DOCS_CHART_HTML)

    return output_path


def write_json_report(report: BenchmarkReport, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path

from __future__ import annotations

from typing import Literal

AsyncifyStatus = Literal["already-async", "changed", "skipped"]
DiagnosticStatus = Literal["already-async", "would-change", "would-skip", "disabled"]
# Pyodide SDL guidance uses await asyncio.sleep(1 / fps) so the browser can
# paint. sleep(0) yields the event loop but often starves paints (esp. Firefox).
# Sleep half a frame budget (1 / (fps * 2)) so frame work + yield can still hit
# the desired FPS instead of always landing below it.
DEFAULT_TARGET_FPS = 60
FRAME_YIELD_HINT = f"await asyncio.sleep(1 / ({DEFAULT_TARGET_FPS} * 2))"
MANUAL_ASYNC_GUIDANCE = (
    f"Make the entrypoint async and add {FRAME_YIELD_HINT} once per frame "
    "(see https://pyodide.org/en/stable/usage/sdl.html)."
)
PYGAME_FRAME_SIGNALS = frozenset(
    {
        "pygame.event.get",
        "pygame.event.pump",
        "pygame.event.wait",
        "pygame.display.update",
        "pygame.display.flip",
    }
)
BLOCKING_CALLS = frozenset(
    {
        "time.sleep",
        "pygame.time.wait",
        "pygame.time.delay",
    }
)

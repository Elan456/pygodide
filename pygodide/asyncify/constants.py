from __future__ import annotations

from typing import Literal

AsyncifyStatus = Literal["already-async", "changed", "skipped"]
DiagnosticStatus = Literal["already-async", "would-change", "would-skip", "disabled"]
MANUAL_ASYNC_GUIDANCE = (
    "Make the entrypoint async and add await asyncio.sleep(0) once per frame."
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

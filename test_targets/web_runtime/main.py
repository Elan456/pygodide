"""Demo: detect whether the game is running in the browser.

Uses the documented check (sys.platform == "emscripten") and fails hard in the
browser if that is wrong so smoke catches regressions. Desktop local runs still
work and label themselves as not-web.
"""

from __future__ import annotations

import asyncio
import sys

import pygame

SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
FPS = 120

BG = (18, 22, 32)
TEXT = (230, 236, 245)
MUTED = (160, 170, 185)
OK = (120, 220, 160)
ERR = (255, 120, 120)


def is_web_runtime() -> bool:
    """True under browser WASM Python (Pyodide / other Emscripten builds)."""
    return sys.platform == "emscripten"


def has_pyodide_js_bridge() -> bool:
    """Ground truth for "we are under Pyodide" (importable only in the browser)."""
    try:
        import js  # noqa: F401  # type: ignore[import-not-found]
    except ImportError:
        return False
    return True


def verify_web_detection() -> str:
    """Return a short status line; raise if the browser case is mis-detected."""
    detected = is_web_runtime()
    under_pyodide = has_pyodide_js_bridge()
    platform = sys.platform
    pyodide_loaded = "pyodide" in sys.modules

    if under_pyodide and not detected:
        raise RuntimeError(
            "Web runtime detection failed under Pyodide. "
            f"Expected sys.platform == 'emscripten', got {platform!r}. "
            f"'pyodide' in sys.modules={pyodide_loaded}, js bridge is importable."
        )

    if detected:
        return (
            f"web=yes  platform={platform}  "
            f"pyodide_module={pyodide_loaded}  js_bridge={under_pyodide}"
        )
    return (
        f"web=no  platform={platform}  "
        f"pyodide_module={pyodide_loaded}  js_bridge={under_pyodide}"
    )


async def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Web runtime detection")
    font = pygame.font.Font(None, 32)
    small = pygame.font.Font(None, 26)
    clock = pygame.time.Clock()

    status = verify_web_detection()
    is_web = is_web_runtime()
    accent = OK if is_web else MUTED

    lines = [
        "Web runtime detection",
        "",
        "Documented check:",
        f"  sys.platform == 'emscripten'  ->  {is_web}",
        f"  sys.platform                 ->  {sys.platform!r}",
        "",
        "Optional (Pyodide-specific, not required for web branching):",
        f"  'pyodide' in sys.modules     ->  {'pyodide' in sys.modules}",
        f"  import js works              ->  {has_pyodide_js_bridge()}",
        "",
        status,
        "",
        "Local desktop: web=no is expected.",
        "Browser (pygodide): web=yes is required.",
    ]

    while True:
        clock.tick(FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return

        screen.fill(BG)
        y = 40
        for index, line in enumerate(lines):
            color = accent if index == 0 or line.startswith("web=") else TEXT
            if "emscripten" in line and "->" in line:
                color = accent if is_web else ERR
            surface = (font if index == 0 else small).render(line, True, color)
            screen.blit(surface, (40, y))
            y += 36 if index == 0 else 28

        pygame.display.update()
        await asyncio.sleep(1 / (FPS * 2))


if __name__ == "__main__":
    asyncio.run(main())

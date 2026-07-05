from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

BrowserEngine = Literal["chromium", "firefox"]

CHROMIUM_UNCAP_ARGS = (
    "--disable-frame-rate-limit",
    "--disable-gpu-vsync",
)

HEADED_CHROMIUM_ARGS = (
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
)


@dataclass(frozen=True)
class BrowserSettings:
    engine: BrowserEngine = "chromium"
    headless: bool = False
    uncap_framerate: bool = False
    use_system_chrome: bool = True

    def describe(self) -> dict[str, Any]:
        chromium_args: list[str] = []
        if self.engine == "chromium":
            if self.uncap_framerate:
                chromium_args.extend(CHROMIUM_UNCAP_ARGS)
            elif not self.headless:
                chromium_args.extend(HEADED_CHROMIUM_ARGS)
        return {
            "engine": self.engine,
            "headless": self.headless,
            "uncap_framerate": self.uncap_framerate,
            "use_system_chrome": self.use_system_chrome,
            "chromium_args": chromium_args,
        }

    def launch(self, playwright: Any) -> Any:
        if self.engine == "firefox":
            prefs: dict[str, int] = {}
            if self.uncap_framerate:
                # Best-effort; Playwright Firefox may still pace near 60 Hz.
                prefs["layout.frame_rate"] = 0
            return playwright.firefox.launch(
                headless=self.headless,
                firefox_user_prefs=prefs or None,
            )

        args: list[str] = []
        if self.uncap_framerate:
            args.extend(CHROMIUM_UNCAP_ARGS)
        elif not self.headless:
            args.extend(HEADED_CHROMIUM_ARGS)

        launch_kwargs: dict[str, Any] = {
            "headless": self.headless,
            "args": args or None,
        }
        if self.use_system_chrome and not self.headless:
            try:
                return playwright.chromium.launch(channel="chrome", **launch_kwargs)
            except Exception:
                pass
        return playwright.chromium.launch(**launch_kwargs)


def ensure_display_available() -> None:
    import os

    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return
    raise RuntimeError(
        "Headed browser benchmarks require a display. "
        "Connect to a graphical session or pass --headless for automation-only runs."
    )

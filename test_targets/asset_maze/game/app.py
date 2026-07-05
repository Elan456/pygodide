from collections.abc import Callable

from game.loaders import (
    load_deep_marker,
    load_root_chime,
    load_title,
    load_ui_badge,
    load_vendor_ping,
    load_waves,
)

AssetCheck = tuple[str, Callable[[], object]]


def collect_asset_checks() -> list[AssetCheck]:
    return [
        ("assets/sprites/nested/deep/marker.png", load_deep_marker),
        ("assets/ui/badge.png", load_ui_badge),
        ("sounds/root_chime.ogg", load_root_chime),
        ("vendor/tiny_sfx/ping.ogg", load_vendor_ping),
        ("data/configs/waves.json", load_waves),
        ("data/strings/title.txt", load_title),
    ]


def verify_assets() -> tuple[list[str], list[str], dict[str, object]]:
    loaded: dict[str, object] = {}
    passed: list[str] = []
    failed: list[str] = []

    for label, loader in collect_asset_checks():
        try:
            loaded[label] = loader()
            passed.append(label)
        except Exception as exc:
            failed.append(f"{label}: {exc}")

    return passed, failed, loaded

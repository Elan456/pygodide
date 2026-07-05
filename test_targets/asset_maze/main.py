import asyncio

import pygame
from game.app import verify_assets

SCREEN_WIDTH, SCREEN_HEIGHT = 960, 640

pygame.init()
pygame.mixer.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Asset Maze")
font = pygame.font.Font(None, 24)
small_font = pygame.font.Font(None, 20)

passed, failed, loaded = verify_assets()
TITLE = str(loaded.get("data/strings/title.txt", "Asset Maze"))


def _draw_line(text: str, y: int, *, color=(220, 230, 245), label_font=font) -> int:
    surface = label_font.render(text, True, color)
    screen.blit(surface, (20, y))
    return y + surface.get_height() + 6


async def main():
    clock = pygame.time.Clock()
    marker = loaded.get("assets/sprites/nested/deep/marker.png")
    badge = loaded.get("assets/ui/badge.png")

    while True:
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if "sounds/root_chime.ogg" in loaded:
                    loaded["sounds/root_chime.ogg"].play()
                if "vendor/tiny_sfx/ping.ogg" in loaded:
                    loaded["vendor/tiny_sfx/ping.ogg"].play()

        screen.fill((12, 18, 30))

        y = 16
        y = _draw_line(TITLE, y, color=(255, 230, 120))
        y = _draw_line("Asset path stress test (auto-discovery staging)", y)
        y = _draw_line(f"Loaded {len(passed)} / {len(passed) + len(failed)} checks", y)
        y += 8

        for label in passed:
            y = _draw_line(
                f"OK  {label}", y, color=(120, 220, 160), label_font=small_font
            )

        for label in failed:
            y = _draw_line(
                f"FAIL {label}", y, color=(255, 140, 140), label_font=small_font
            )

        if marker is not None:
            screen.blit(marker, (SCREEN_WIDTH - 120, 24))
        if badge is not None:
            screen.blit(badge, (SCREEN_WIDTH - 56, 24))

        y = max(y + 12, 360)
        _draw_line("SPACE: play staged sounds   ESC: quit", y, label_font=small_font)

        pygame.display.flip()
        await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())

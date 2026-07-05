import asyncio

import pygame

SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600

pygame.init()
pygame.mixer.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Pygodide Mixer Test")
font = pygame.font.Font(None, 30)

pygame.mixer.music.load("sounds/cropped-dirt-rhodes-by-kevin-macleod.mp3")
sfx = {
    pygame.K_1: pygame.mixer.Sound("sounds/click.ogg"),
    pygame.K_2: pygame.mixer.Sound("sounds/confirm.ogg"),
    pygame.K_3: pygame.mixer.Sound("sounds/bounce.ogg"),
}
SFX_COLORS = {
    pygame.K_1: (80, 180, 255),
    pygame.K_2: (120, 220, 160),
    pygame.K_3: (255, 200, 80),
}
SFX_KEYS = (pygame.K_1, pygame.K_2, pygame.K_3)
BOX_SIZE = 80
BOX_GAP = 28
BOX_ROW_WIDTH = len(SFX_KEYS) * BOX_SIZE + (len(SFX_KEYS) - 1) * BOX_GAP
BOX_Y = (SCREEN_HEIGHT - BOX_SIZE) // 2
BOX_X0 = (SCREEN_WIDTH - BOX_ROW_WIDTH) // 2
SFX_RECTS = {
    key: pygame.Rect(
        BOX_X0 + index * (BOX_SIZE + BOX_GAP),
        BOX_Y,
        BOX_SIZE,
        BOX_SIZE,
    )
    for index, key in enumerate(SFX_KEYS)
}
FLASH_MS = 180

HELP_LINES = [
    "Mixer test",
    "SPACE or click: play / pause music",
    "1 / 2 / 3: sound effects",
    "S: stop music",
]


async def main():
    clock = pygame.time.Clock()
    music_state = "off"
    flash_until = dict.fromkeys(sfx, 0)

    def play_sfx(key: int) -> None:
        sfx[key].play()
        flash_until[key] = pygame.time.get_ticks() + FLASH_MS

    while True:
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return

            if event.type == pygame.MOUSEBUTTONDOWN or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE
            ):
                if music_state == "off":
                    pygame.mixer.music.play(-1)
                    music_state = "playing"
                elif music_state == "playing":
                    pygame.mixer.music.pause()
                    music_state = "paused"
                else:
                    pygame.mixer.music.unpause()
                    music_state = "playing"
                continue

            if event.type != pygame.KEYDOWN:
                continue

            if event.key == pygame.K_s:
                pygame.mixer.music.stop()
                music_state = "off"
            elif event.key in sfx:
                play_sfx(event.key)

        screen.fill((10, 16, 28))

        now = pygame.time.get_ticks()
        for key in SFX_KEYS:
            rect = SFX_RECTS[key]
            color = SFX_COLORS[key]
            pygame.draw.rect(screen, color, rect, width=2)
            if now < flash_until[key] and (flash_until[key] - now) // 60 % 2 == 0:
                pygame.draw.rect(screen, color, rect)
            label = font.render(str(key - pygame.K_0), True, color)
            screen.blit(label, label.get_rect(center=rect.center))

        y = 24
        for line in HELP_LINES:
            screen.blit(font.render(line, True, (230, 236, 245)), (24, y))
            y += 36

        screen.blit(
            font.render(f"music {music_state}", True, (255, 240, 120)),
            (24, y),
        )

        pygame.display.flip()
        await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())

"""Async entrypoint that never yields — hang watchdog demo.

This fixture intentionally never yields to the event loop so the browser main
thread freezes. Pygodide should show hang guidance (painted before the
entrypoint runs) instead of a blank frozen canvas with no help.
"""

import pygame

# Do init here
# Load any assets right now to avoid lag at runtime or network errors.

SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Async hang watchdog demo")


async def main():
    clock = pygame.time.Clock()
    x = 0

    # Tight async loop with no await: freezes the browser the same way a sync
    # while-loop does. Hang help must already be on screen.
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return

        screen.fill((20, 24, 40))
        pygame.draw.circle(
            screen,
            (220, 80, 80),
            (x % SCREEN_WIDTH, SCREEN_HEIGHT // 2),
            40,
        )
        x += 8
        pygame.display.flip()
        clock.tick(120)
        # Intentionally no frame yield (hang watchdog fixture).


if __name__ == "__main__":
    # Local runs would also hang without a yield; this file is a browser fixture.
    import asyncio

    asyncio.run(main())

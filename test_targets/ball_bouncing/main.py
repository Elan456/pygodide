import asyncio

import pygame
from ball import Ball

# Do init here
# Load any assets right now to avoid lag at runtime or network errors.

SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Pygame WASM Example")
font = pygame.font.Font(None, 30)


async def main():
    ball = Ball(pygame.Color("white"), 20)
    clock = pygame.time.Clock()

    while True:
        dt = min(clock.tick() / 1000.0, 1 / 30)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN:
                # All 4 arrow keys accelerate the ball in their respective direction
                if event.key == pygame.K_UP:
                    ball.nudge(0, -1)
                if event.key == pygame.K_DOWN:
                    ball.nudge(0, 1)
                if event.key == pygame.K_LEFT:
                    ball.nudge(-1, 0)
                if event.key == pygame.K_RIGHT:
                    ball.nudge(1, 0)

        screen.fill((0, 0, 0))
        ball.update(screen, dt)
        ball.draw(screen)

        fps_text = font.render(
            f"FPS: {clock.get_fps():.0f}",
            True,
            pygame.Color("white"),
        )
        screen.blit(fps_text, (10, 10))

        pygame.display.update()
        clock.tick(120)

        # Yield to the event loop to allow the browser to update the screen
        # and handle events.
        await asyncio.sleep(1 / (120 * 2))


if __name__ == "__main__":
    asyncio.run(main())

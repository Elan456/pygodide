import asyncio

import pygame
from ball import Ball

# Do init here
# Load any assets right now to avoid lag at runtime or network errors.

SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Pygame WASM Example")


async def main():
    ball = Ball(pygame.Color("white"), 20)
    clock = pygame.time.Clock()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN:
                # All 4 arrow keys accelerate the ball in their respective direction
                if event.key == pygame.K_UP:
                    ball.nudge(0, -10)
                if event.key == pygame.K_DOWN:
                    ball.nudge(0, 10)
                if event.key == pygame.K_LEFT:
                    ball.nudge(-10, 0)
                if event.key == pygame.K_RIGHT:
                    ball.nudge(10, 0)

        screen.fill((0, 0, 0))
        ball.update(screen)
        ball.draw(screen)

        pygame.display.update()

        clock.tick(60)  # Limit to 60 FPS

        await asyncio.sleep(0)  # Very important, and keep it 0

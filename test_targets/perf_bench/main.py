import asyncio
import random
import time

import pygame
from benchmark import BenchmarkSampler
from entities import (
    ENEMY_RADIUS,
    PLAYER_RADIUS,
    STAR_RADIUS,
    Player,
    Star,
    make_background_stars,
    make_enemies,
)

SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
ENEMY_COUNT = 18
STAR_COUNT = 10
BACKGROUND_STAR_COUNT = 48

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Perf Bench — Dodge Arena")
font = pygame.font.Font(None, 28)
small_font = pygame.font.Font(None, 22)

rng = random.Random(17)
play_bounds = screen.get_rect().inflate(-24, -24)
benchmark = BenchmarkSampler()
player = Player((SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2))
enemies = make_enemies(ENEMY_COUNT, play_bounds, rng)
stars = pygame.sprite.Group()
for _ in range(STAR_COUNT):
    star = Star((SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2))
    star.respawn(play_bounds, rng)
    stars.add(star)
background_stars = make_background_stars(BACKGROUND_STAR_COUNT, play_bounds, rng)
score = 0
RESPAWN_INVULN_SECONDS = 0.6
player_invuln_until = 0.0


def _distance_sq(
    a: pygame.math.Vector2,
    b: pygame.math.Vector2,
) -> float:
    delta = a - b
    return delta.length_squared()


def _handle_collisions() -> None:
    global score, player_invuln_until

    pickup_radius = PLAYER_RADIUS + STAR_RADIUS
    pickup_radius_sq = pickup_radius * pickup_radius
    for star in stars:
        if _distance_sq(player.position, star.position) <= pickup_radius_sq:
            score += 1
            star.respawn(play_bounds, rng)

    now = time.monotonic()
    if now < player_invuln_until:
        return

    hit_radius = PLAYER_RADIUS + ENEMY_RADIUS
    hit_radius_sq = hit_radius * hit_radius
    for enemy in enemies:
        if _distance_sq(player.position, enemy.position) <= hit_radius_sq:
            player.position.update(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
            player.rect.center = (int(player.position.x), int(player.position.y))
            player_invuln_until = now + RESPAWN_INVULN_SECONDS
            break


def _draw_hud() -> None:
    lines = [f"Score: {score}", *benchmark.hud_lines(), "Move: WASD / arrows"]
    y = 10
    for index, line in enumerate(lines):
        is_hint = line.startswith("Move:")
        text_font = small_font if is_hint else font
        if is_hint:
            color = pygame.Color(180, 190, 210)
        elif line.startswith("FPS mean:") or line == "Bench: done":
            color = pygame.Color("gold")
        else:
            color = pygame.Color("white")
        surface = text_font.render(line, True, color)
        screen.blit(surface, (10, y))
        y += surface.get_height() + 2


async def main() -> None:
    clock = pygame.time.Clock()

    while True:
        dt = min(clock.tick(0) / 1000.0, 1 / 30)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return

        keys = pygame.key.get_pressed()
        player.update(keys, play_bounds, dt)
        for enemy in enemies:
            enemy.update(dt)
        _handle_collisions()

        screen.fill((10, 14, 28))
        for x, y, color in background_stars:
            screen.set_at((x, y), color)
        for enemy in enemies:
            screen.blit(enemy.image, enemy.rect)
        stars.draw(screen)
        screen.blit(player.image, player.rect)

        benchmark.on_frame(clock.get_fps())
        _draw_hud()

        pygame.display.update()

        await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(main())

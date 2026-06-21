import asyncio

import numpy as np
import pygame

SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
PARTICLE_COUNT = 36
PLAYER_RADIUS = 18
PARTICLE_BASE_RADIUS = 10
PLAYER_SPEED = 280.0

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("NumPy Particle Field")
font = pygame.font.Font(None, 30)

rng = np.random.default_rng(7)
particle_positions = rng.uniform(
    low=(80.0, 80.0),
    high=(SCREEN_WIDTH - 80.0, SCREEN_HEIGHT - 80.0),
    size=(PARTICLE_COUNT, 2),
)
particle_velocities = rng.uniform(-140.0, 140.0, size=(PARTICLE_COUNT, 2))
particle_phases = rng.uniform(0.0, np.pi * 2.0, size=PARTICLE_COUNT)
player_position = np.array([SCREEN_WIDTH / 2.0, SCREEN_HEIGHT / 2.0], dtype=float)


def _move_player(dt: float) -> None:
    pressed = pygame.key.get_pressed()
    direction = np.array(
        [
            float(pressed[pygame.K_RIGHT]) - float(pressed[pygame.K_LEFT]),
            float(pressed[pygame.K_DOWN]) - float(pressed[pygame.K_UP]),
        ],
        dtype=float,
    )

    magnitude = np.linalg.norm(direction)
    if magnitude > 0.0:
        direction /= magnitude
        player_position[:] += direction * PLAYER_SPEED * dt

    player_position[0] = np.clip(
        player_position[0], PLAYER_RADIUS, SCREEN_WIDTH - PLAYER_RADIUS
    )
    player_position[1] = np.clip(
        player_position[1], PLAYER_RADIUS, SCREEN_HEIGHT - PLAYER_RADIUS
    )


def _update_particles(dt: float) -> None:
    particle_positions[:] += particle_velocities * dt

    x_low = particle_positions[:, 0] < PARTICLE_BASE_RADIUS
    x_high = particle_positions[:, 0] > SCREEN_WIDTH - PARTICLE_BASE_RADIUS
    y_low = particle_positions[:, 1] < PARTICLE_BASE_RADIUS
    y_high = particle_positions[:, 1] > SCREEN_HEIGHT - PARTICLE_BASE_RADIUS

    particle_velocities[x_low | x_high, 0] *= -1.0
    particle_velocities[y_low | y_high, 1] *= -1.0

    particle_positions[:, 0] = np.clip(
        particle_positions[:, 0],
        PARTICLE_BASE_RADIUS,
        SCREEN_WIDTH - PARTICLE_BASE_RADIUS,
    )
    particle_positions[:, 1] = np.clip(
        particle_positions[:, 1],
        PARTICLE_BASE_RADIUS,
        SCREEN_HEIGHT - PARTICLE_BASE_RADIUS,
    )


def _collect_particles(now_seconds: float) -> int:
    offsets = particle_positions - player_position
    distances = np.linalg.norm(offsets, axis=1)
    radii = PARTICLE_BASE_RADIUS + 4.0 * np.sin(now_seconds * 3.0 + particle_phases)
    collected = distances < (PLAYER_RADIUS + radii)
    collected_count = int(np.count_nonzero(collected))

    if collected_count:
        particle_positions[collected] = rng.uniform(
            low=(80.0, 80.0),
            high=(SCREEN_WIDTH - 80.0, SCREEN_HEIGHT - 80.0),
            size=(collected_count, 2),
        )
        particle_velocities[collected] = rng.uniform(
            -160.0, 160.0, size=(collected_count, 2)
        )
        particle_phases[collected] = rng.uniform(0.0, np.pi * 2.0, size=collected_count)

    return collected_count


def _draw_scene(score: int, now_seconds: float) -> None:
    screen.fill((8, 12, 24))

    radii = PARTICLE_BASE_RADIUS + 4.0 * np.sin(now_seconds * 3.0 + particle_phases)
    glow = 120 + 100 * np.sin(now_seconds * 2.5 + particle_phases)

    for (x_pos, y_pos), radius, color_shift in zip(
        particle_positions, radii, glow, strict=False
    ):
        pygame.draw.circle(
            screen,
            (80, int(color_shift), 240),
            (int(x_pos), int(y_pos)),
            int(radius),
        )

    pygame.draw.circle(
        screen,
        (255, 240, 120),
        (int(player_position[0]), int(player_position[1])),
        PLAYER_RADIUS,
    )

    caption = font.render(f"Score: {score}", True, pygame.Color("white"))
    hint = font.render(
        "Move with arrow keys and collect the particles", True, (180, 190, 220)
    )
    screen.blit(caption, (20, 20))
    screen.blit(hint, (20, 50))
    pygame.display.flip()


async def main():
    clock = pygame.time.Clock()
    score = 0

    while True:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return

        _move_player(dt)
        _update_particles(dt)

        now_seconds = pygame.time.get_ticks() / 1000.0
        score += _collect_particles(now_seconds)
        _draw_scene(score, now_seconds)

        await asyncio.sleep(0)

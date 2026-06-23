import asyncio
import math

import fastquadtree as fqt
import numpy as np
import pygame

SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
PARTICLE_COUNT = 36
PLAYER_RADIUS = 18
PARTICLE_BASE_RADIUS = 10
PARTICLE_RADIUS_SWAY = 4
PARTICLE_MAX_RADIUS = PARTICLE_BASE_RADIUS + PARTICLE_RADIUS_SWAY
PLAYER_SPEED = 280.0
QUADTREE_CAPACITY = 4
QUADTREE_MAX_DEPTH = 6

BACKGROUND_COLOR = (8, 12, 24)
PLAYER_COLOR = (255, 240, 120)
QUADTREE_COLOR = (64, 180, 156)

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("FastQuadtree Particle Field")
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
quadtree = fqt.Quadtree(
    (0.0, 0.0, float(SCREEN_WIDTH), float(SCREEN_HEIGHT)),
    QUADTREE_CAPACITY,
    max_depth=QUADTREE_MAX_DEPTH,
)


def _random_positions(count: int) -> np.ndarray:
    return rng.uniform(
        low=(80.0, 80.0),
        high=(SCREEN_WIDTH - 80.0, SCREEN_HEIGHT - 80.0),
        size=(count, 2),
    )


def _random_velocities(count: int) -> np.ndarray:
    return rng.uniform(-160.0, 160.0, size=(count, 2))


def _particle_radii(now_seconds: float) -> np.ndarray:
    return PARTICLE_BASE_RADIUS + PARTICLE_RADIUS_SWAY * np.sin(
        now_seconds * 3.0 + particle_phases
    )


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


def _update_particles(dt: float, radii: np.ndarray) -> None:
    particle_positions[:] += particle_velocities * dt
    _contain_particles(radii)


def _contain_particles(radii: np.ndarray) -> None:
    x_low = particle_positions[:, 0] < radii
    x_high = particle_positions[:, 0] > SCREEN_WIDTH - radii
    y_low = particle_positions[:, 1] < radii
    y_high = particle_positions[:, 1] > SCREEN_HEIGHT - radii

    particle_velocities[x_low | x_high, 0] *= -1.0
    particle_velocities[y_low | y_high, 1] *= -1.0

    particle_positions[:, 0] = np.clip(
        particle_positions[:, 0], radii, SCREEN_WIDTH - radii
    )
    particle_positions[:, 1] = np.clip(
        particle_positions[:, 1], radii, SCREEN_HEIGHT - radii
    )


def _rebuild_quadtree() -> None:
    quadtree.clear()
    quadtree.insert_many_np(np.asarray(particle_positions, dtype=np.float32))


def _resolve_particle_collisions(radii: np.ndarray) -> int:
    collision_count = 0

    for index, position in enumerate(particle_positions):
        search_radius = float(radii[index] + PARTICLE_MAX_RADIUS)
        bounds = (
            float(position[0] - search_radius),
            float(position[1] - search_radius),
            float(position[0] + search_radius),
            float(position[1] + search_radius),
        )
        neighbor_ids, _ = quadtree.query_np(bounds)

        for neighbor_raw in neighbor_ids:
            neighbor_index = int(neighbor_raw)
            if neighbor_index <= index:
                continue

            delta = particle_positions[neighbor_index] - position
            distance_sq = float(np.dot(delta, delta))
            min_distance = float(radii[index] + radii[neighbor_index])

            if distance_sq >= min_distance * min_distance:
                continue

            if distance_sq == 0.0:
                angle = rng.uniform(0.0, np.pi * 2.0)
                normal = np.array([math.cos(angle), math.sin(angle)], dtype=float)
                distance = 1e-6
            else:
                distance = math.sqrt(distance_sq)
                normal = delta / distance

            overlap = min_distance - distance
            particle_positions[index] -= normal * (overlap * 0.5)
            particle_positions[neighbor_index] += normal * (overlap * 0.5)

            separating_speed = float(
                np.dot(
                    particle_velocities[neighbor_index] - particle_velocities[index],
                    normal,
                )
            )
            if separating_speed < 0.0:
                impulse = normal * separating_speed
                particle_velocities[index] += impulse
                particle_velocities[neighbor_index] -= impulse

            collision_count += 1

    _contain_particles(radii)
    return collision_count


def _collect_particles(radii: np.ndarray) -> int:
    search_radius = PLAYER_RADIUS + PARTICLE_MAX_RADIUS
    bounds = (
        float(player_position[0] - search_radius),
        float(player_position[1] - search_radius),
        float(player_position[0] + search_radius),
        float(player_position[1] + search_radius),
    )
    candidate_ids, _ = quadtree.query_np(bounds)

    if len(candidate_ids) == 0:
        return 0

    collected_ids: list[int] = []
    for candidate_raw in candidate_ids:
        index = int(candidate_raw)
        offset = particle_positions[index] - player_position
        distance = float(np.linalg.norm(offset))
        if distance < (PLAYER_RADIUS + radii[index]):
            collected_ids.append(index)

    collected_count = len(collected_ids)
    if collected_count == 0:
        return 0

    collected = np.array(collected_ids, dtype=int)
    particle_positions[collected] = _random_positions(collected_count)
    particle_velocities[collected] = _random_velocities(collected_count)
    particle_phases[collected] = rng.uniform(0.0, np.pi * 2.0, size=collected_count)

    return collected_count


def _draw_scene(
    score: int, now_seconds: float, radii: np.ndarray, collision_count: int
) -> None:
    screen.fill(BACKGROUND_COLOR)

    glow = 120 + 100 * np.sin(now_seconds * 2.5 + particle_phases)
    node_bounds = quadtree.get_all_node_boundaries()

    for bounds in node_bounds:
        left, top, right, bottom = bounds
        rect = pygame.Rect(
            int(left),
            int(top),
            max(1, int(right - left)),
            max(1, int(bottom - top)),
        )
        pygame.draw.rect(screen, QUADTREE_COLOR, rect, width=1)

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
        PLAYER_COLOR,
        (int(player_position[0]), int(player_position[1])),
        PLAYER_RADIUS,
    )

    node_count = len(node_bounds)
    caption = font.render(f"Score: {score}", True, pygame.Color("white"))
    stats = font.render(
        f"Nodes: {node_count}  Particle collisions: {collision_count}",
        True,
        (210, 226, 238),
    )
    hint = font.render(
        "Move with arrow keys and collect particles inside the quadtree overlay",
        True,
        (180, 190, 220),
    )
    screen.blit(caption, (20, 20))
    screen.blit(stats, (20, 50))
    screen.blit(hint, (20, 80))
    pygame.display.flip()


def loop(clock, score):
    dt = clock.tick(60) / 1000.0

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return

    now_seconds = pygame.time.get_ticks() / 1000.0
    radii = _particle_radii(now_seconds)

    _move_player(dt)
    _update_particles(dt, radii)
    _rebuild_quadtree()
    collision_count = _resolve_particle_collisions(radii)
    _rebuild_quadtree()

    score += _collect_particles(radii)
    radii = _particle_radii(now_seconds)
    _rebuild_quadtree()
    _draw_scene(score, now_seconds, radii, collision_count)


def main():
    asyncio.run(web_main())


async def web_main():
    clock = pygame.time.Clock()
    score = 0

    while True:
        loop(clock, score)
        await asyncio.sleep(0)


if __name__ == "__main__":
    main()

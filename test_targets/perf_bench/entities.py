from __future__ import annotations

import random

import pygame

REFERENCE_FPS = 60
ENEMY_SPEED = 120.0
PLAYER_SPEED = 260.0
STAR_RADIUS = 10
PLAYER_RADIUS = 14
ENEMY_RADIUS = 16


def _make_circle_surface(radius: int, color: pygame.Color) -> pygame.Surface:
    diameter = radius * 2
    surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    pygame.draw.circle(surface, color, (radius, radius), radius)
    return surface


class Player(pygame.sprite.Sprite):
    def __init__(self, position: tuple[float, float]) -> None:
        super().__init__()
        self.radius = PLAYER_RADIUS
        self.image = _make_circle_surface(self.radius, pygame.Color("cyan"))
        self.rect = self.image.get_rect(center=(int(position[0]), int(position[1])))
        self.position = pygame.math.Vector2(position)

    def update(
        self, keys: pygame.key.ScancodeWrapper, bounds: pygame.Rect, dt: float
    ) -> None:
        direction = pygame.math.Vector2(
            float(keys[pygame.K_RIGHT] or keys[pygame.K_d])
            - float(keys[pygame.K_LEFT] or keys[pygame.K_a]),
            float(keys[pygame.K_DOWN] or keys[pygame.K_s])
            - float(keys[pygame.K_UP] or keys[pygame.K_w]),
        )
        if direction.length_squared() > 0:
            direction = direction.normalize()
        self.position += direction * PLAYER_SPEED * dt
        self.position.x = max(
            bounds.left + self.radius,
            min(bounds.right - self.radius, self.position.x),
        )
        self.position.y = max(
            bounds.top + self.radius,
            min(bounds.bottom - self.radius, self.position.y),
        )
        self.rect.center = (int(self.position.x), int(self.position.y))


class Enemy(pygame.sprite.Sprite):
    def __init__(
        self,
        *,
        position: tuple[float, float],
        velocity: tuple[float, float],
        color: pygame.Color,
        bounds: pygame.Rect,
    ) -> None:
        super().__init__()
        self.radius = ENEMY_RADIUS
        self.bounds = bounds
        self.image = _make_circle_surface(self.radius, color)
        self.rect = self.image.get_rect(center=(int(position[0]), int(position[1])))
        self.position = pygame.math.Vector2(position)
        self.velocity = pygame.math.Vector2(velocity)

    def update(self, dt: float) -> None:
        self.position += self.velocity * dt

        if self.position.x - self.radius < self.bounds.left:
            self.position.x = self.bounds.left + self.radius
            if self.velocity.x < 0:
                self.velocity.x *= -1
        elif self.position.x + self.radius > self.bounds.right:
            self.position.x = self.bounds.right - self.radius
            if self.velocity.x > 0:
                self.velocity.x *= -1

        if self.position.y - self.radius < self.bounds.top:
            self.position.y = self.bounds.top + self.radius
            if self.velocity.y < 0:
                self.velocity.y *= -1
        elif self.position.y + self.radius > self.bounds.bottom:
            self.position.y = self.bounds.bottom - self.radius
            if self.velocity.y > 0:
                self.velocity.y *= -1

        self.rect.center = (int(self.position.x), int(self.position.y))


class Star(pygame.sprite.Sprite):
    def __init__(self, position: tuple[float, float]) -> None:
        super().__init__()
        self.radius = STAR_RADIUS
        self.image = _make_circle_surface(self.radius, pygame.Color("gold"))
        self.rect = self.image.get_rect(center=(int(position[0]), int(position[1])))
        self.position = pygame.math.Vector2(position)

    def respawn(self, bounds: pygame.Rect, rng: random.Random) -> None:
        margin = self.radius + 8
        self.position.update(
            rng.uniform(bounds.left + margin, bounds.right - margin),
            rng.uniform(bounds.top + margin, bounds.bottom - margin),
        )
        self.rect.center = (int(self.position.x), int(self.position.y))


def make_enemies(
    count: int,
    bounds: pygame.Rect,
    rng: random.Random,
) -> list[Enemy]:
    palette = [
        pygame.Color("tomato"),
        pygame.Color("orange"),
        pygame.Color("mediumpurple"),
        pygame.Color("lightgreen"),
        pygame.Color("hotpink"),
    ]
    enemies: list[Enemy] = []
    for index in range(count):
        margin = ENEMY_RADIUS + 12
        position = (
            rng.uniform(bounds.left + margin, bounds.right - margin),
            rng.uniform(bounds.top + margin, bounds.bottom - margin),
        )
        angle = rng.uniform(0.0, 6.28318)
        speed = rng.uniform(ENEMY_SPEED * 0.75, ENEMY_SPEED * 1.25)
        velocity = speed * pygame.math.Vector2(1, 0).rotate_rad(angle)
        enemies.append(
            Enemy(
                position=position,
                velocity=(velocity.x, velocity.y),
                color=palette[index % len(palette)],
                bounds=bounds,
            )
        )
    return enemies


def make_background_stars(
    count: int,
    bounds: pygame.Rect,
    rng: random.Random,
) -> list[tuple[int, int, pygame.Color]]:
    colors = [
        pygame.Color(40, 48, 72),
        pygame.Color(55, 64, 92),
        pygame.Color(72, 82, 112),
    ]
    stars: list[tuple[int, int, pygame.Color]] = []
    for _ in range(count):
        stars.append(
            (
                rng.randint(bounds.left + 4, bounds.right - 4),
                rng.randint(bounds.top + 4, bounds.bottom - 4),
                rng.choice(colors),
            )
        )
    return stars

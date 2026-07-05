import pygame

REFERENCE_FPS = 60
# Original values were per-frame at ~60 FPS; velocity is now px/s.
GRAVITY = 0.5 * REFERENCE_FPS * REFERENCE_FPS
FRICTION = 0.99
NUDGE_IMPULSE = 10 * REFERENCE_FPS


class Ball(pygame.sprite.Sprite):
    def __init__(self, color, radius):
        super().__init__()
        self.radius = radius
        diameter = radius * 2
        self.image: pygame.Surface = pygame.Surface(
            (diameter, diameter),
            pygame.SRCALPHA,
        )
        pygame.draw.circle(self.image, color, (radius, radius), radius)
        self.rect: pygame.Rect = self.image.get_rect()
        self.position = pygame.math.Vector2(self.rect.topleft)
        self.velocity: pygame.math.Vector2 = pygame.math.Vector2(0, 0)

    def update(self, surface: pygame.Surface, dt: float):
        self.position += self.velocity * dt
        self.velocity.y += GRAVITY * dt
        friction = FRICTION ** (dt * REFERENCE_FPS)
        self.velocity *= friction

        width = surface.get_width()
        height = surface.get_height()
        diameter = self.radius * 2

        if self.position.x < 0:
            self.position.x = 0
            if self.velocity.x < 0:
                self.velocity.x *= -1
        elif self.position.x + diameter > width:
            self.position.x = width - diameter
            if self.velocity.x > 0:
                self.velocity.x *= -1

        if self.position.y < 0:
            self.position.y = 0
            if self.velocity.y < 0:
                self.velocity.y *= -1
        elif self.position.y + diameter > height:
            self.position.y = height - diameter
            if self.velocity.y > 0:
                self.velocity.y *= -1

        self.rect.topleft = (int(self.position.x), int(self.position.y))

    def draw(self, surface: pygame.Surface):
        surface.blit(self.image, self.rect)

    def nudge(self, x: float, y: float):
        self.velocity.x += x * NUDGE_IMPULSE
        self.velocity.y += y * NUDGE_IMPULSE

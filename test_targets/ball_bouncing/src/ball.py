import pygame

class Ball(pygame.sprite.Sprite):
    def __init__(self, color, radius):
        super().__init__()
        self.image: pygame.Surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, color, (radius, radius), radius)
        self.rect: pygame.Rect = self.image.get_rect()
        self.velocity: pygame.math.Vector2 = pygame.math.Vector2(0, 0)

    def update(self, surface: pygame.Surface):
        self.rect.x += self.velocity.x
        self.rect.y += self.velocity.y
        self.velocity.y += 0.5  # Gravity effect
        self.velocity.x *= 0.99  # Friction effect
        self.velocity.y *= 0.99  # Friction effect

        # Use surface for wall/floor/celling collision + bouncing
        if self.rect.left < 0:
            self.rect.left = 0
            self.velocity.x *= -1
        if self.rect.right > surface.get_width():
            self.rect.right = surface.get_width()
            self.velocity.x *= -1
        if self.rect.top < 0:
            self.rect.top = 0
            self.velocity.y *= -1
        if self.rect.bottom > surface.get_height():
            self.rect.bottom = surface.get_height()
            self.velocity.y *= -1

    def draw(self, surface: pygame.Surface):
        surface.blit(self.image, self.rect)

    def nudge(self, x, y):
        self.velocity.x += x
        self.velocity.y += y

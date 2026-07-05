import pygame
from ball import Ball

SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Sync Event Pump Loop")


def main():
    ball = Ball(pygame.Color("white"), 20)
    clock = pygame.time.Clock()

    while True:
        pygame.event.pump()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN:
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
        clock.tick(60)


if __name__ == "__main__":
    main()

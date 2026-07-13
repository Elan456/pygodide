"""Demo: drag colored boxes and persist their positions to save-slot files.

Shows that ordinary Python file I/O (open / pathlib) works under pygodide:
create a saves/ directory, write JSON per slot, and read it back.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pygame

SCREEN_WIDTH, SCREEN_HEIGHT = 900, 600
PLAY_AREA = pygame.Rect(20, 70, 560, 500)
PANEL = pygame.Rect(600, 70, 280, 500)

BOX_SIZE = 64
SAVES_DIR = Path("saves")
SLOT_COUNT = 3

# Default spawn positions inside the play area (top-left of each box).
DEFAULT_POSITIONS: dict[str, tuple[int, int]] = {
    "red": (80, 140),
    "green": (220, 260),
    "blue": (360, 380),
}

BOX_COLORS: dict[str, tuple[int, int, int]] = {
    "red": (220, 70, 70),
    "green": (70, 190, 100),
    "blue": (70, 130, 230),
}

BG = (18, 22, 32)
PANEL_BG = (28, 34, 48)
PLAY_BG = (24, 28, 40)
TEXT = (230, 236, 245)
MUTED = (160, 170, 185)
OK = (120, 220, 160)
WARN = (255, 200, 80)
ERR = (255, 120, 120)
BTN_SAVE = (55, 120, 90)
BTN_LOAD = (55, 95, 150)
BTN_HOVER = (255, 255, 255)


def slot_path(slot: int) -> Path:
    return SAVES_DIR / f"slot_{slot}.json"


def ensure_saves_dir() -> None:
    SAVES_DIR.mkdir(parents=True, exist_ok=True)


def save_slot(slot: int, boxes: dict[str, pygame.Rect]) -> str:
    ensure_saves_dir()
    path = slot_path(slot)
    payload = {
        "slot": slot,
        "boxes": {name: {"x": rect.x, "y": rect.y} for name, rect in boxes.items()},
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return f"Saved slot {slot} -> {path}"


def load_slot(slot: int, boxes: dict[str, pygame.Rect]) -> str:
    path = slot_path(slot)
    if not path.is_file():
        return f"Slot {slot} is empty ({path} missing)"
    data = json.loads(path.read_text(encoding="utf-8"))
    for name, pos in data.get("boxes", {}).items():
        if name not in boxes:
            continue
        boxes[name].x = int(pos["x"])
        boxes[name].y = int(pos["y"])
        clamp_box(boxes[name])
    return f"Loaded slot {slot} from {path}"


def clamp_box(rect: pygame.Rect) -> None:
    rect.x = max(PLAY_AREA.left, min(rect.x, PLAY_AREA.right - rect.width))
    rect.y = max(PLAY_AREA.top, min(rect.y, PLAY_AREA.bottom - rect.height))


def make_boxes() -> dict[str, pygame.Rect]:
    boxes: dict[str, pygame.Rect] = {}
    for name, (x, y) in DEFAULT_POSITIONS.items():
        rect = pygame.Rect(x, y, BOX_SIZE, BOX_SIZE)
        clamp_box(rect)
        boxes[name] = rect
    return boxes


def box_at(pos: tuple[int, int], boxes: dict[str, pygame.Rect]) -> str | None:
    # Topmost first: reverse draw order (blue drawn last).
    for name in reversed(list(boxes)):
        if boxes[name].collidepoint(pos):
            return name
    return None


class Button:
    def __init__(
        self,
        rect: pygame.Rect,
        label: str,
        color: tuple[int, int, int],
        action: str,
        slot: int,
    ) -> None:
        self.rect = rect
        self.label = label
        self.color = color
        self.action = action
        self.slot = slot

    def hit(self, pos: tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)


def build_buttons() -> list[Button]:
    buttons: list[Button] = []
    for index in range(SLOT_COUNT):
        slot = index + 1
        row_y = PANEL.top + 56 + index * 120
        save_rect = pygame.Rect(PANEL.left + 20, row_y + 36, 110, 40)
        load_rect = pygame.Rect(PANEL.left + 150, row_y + 36, 110, 40)
        buttons.append(Button(save_rect, "Save", BTN_SAVE, "save", slot))
        buttons.append(Button(load_rect, "Load", BTN_LOAD, "load", slot))
    return buttons


def draw_button(
    surface: pygame.Surface,
    button: Button,
    font: pygame.font.Font,
    hover: bool,
) -> None:
    color = button.color
    pygame.draw.rect(surface, color, button.rect, border_radius=6)
    border = BTN_HOVER if hover else (20, 24, 32)
    pygame.draw.rect(
        surface, border, button.rect, width=2 if hover else 1, border_radius=6
    )
    label = font.render(button.label, True, TEXT)
    surface.blit(label, label.get_rect(center=button.rect.center))


def slot_has_file(slot: int) -> bool:
    return slot_path(slot).is_file()


async def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Save Slots — file I/O demo")
    title_font = pygame.font.Font(None, 36)
    body_font = pygame.font.Font(None, 28)
    small_font = pygame.font.Font(None, 24)

    boxes = make_boxes()
    buttons = build_buttons()
    clock = pygame.time.Clock()

    dragging: str | None = None
    drag_offset = (0, 0)
    status = "Drag boxes, then Save / Load a slot."
    status_color = MUTED

    ensure_saves_dir()
    print(f"[save_slots] saves directory: {SAVES_DIR.resolve()}", flush=True)

    while True:
        clock.tick(120)
        mouse = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                hit = box_at(event.pos, boxes)
                if hit is not None:
                    dragging = hit
                    rect = boxes[hit]
                    drag_offset = (event.pos[0] - rect.x, event.pos[1] - rect.y)
                    continue

                for button in buttons:
                    if not button.hit(event.pos):
                        continue
                    try:
                        if button.action == "save":
                            status = save_slot(button.slot, boxes)
                            status_color = OK
                            print(f"[save_slots] {status}", flush=True)
                        else:
                            status = load_slot(button.slot, boxes)
                            status_color = OK if slot_has_file(button.slot) else WARN
                            print(f"[save_slots] {status}", flush=True)
                    except OSError as exc:
                        status = f"File error: {exc}"
                        status_color = ERR
                        print(f"[save_slots] {status}", flush=True)
                    except (
                        json.JSONDecodeError,
                        KeyError,
                        TypeError,
                        ValueError,
                    ) as exc:
                        status = f"Bad save data: {exc}"
                        status_color = ERR
                        print(f"[save_slots] {status}", flush=True)
                    break

            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                dragging = None

            if event.type == pygame.MOUSEMOTION and dragging is not None:
                rect = boxes[dragging]
                rect.x = event.pos[0] - drag_offset[0]
                rect.y = event.pos[1] - drag_offset[1]
                clamp_box(rect)

        screen.fill(BG)

        screen.blit(title_font.render("Save Slots (file I/O)", True, TEXT), (20, 18))
        screen.blit(
            small_font.render(
                "Drag red / green / blue boxes. Each slot writes saves/slot_N.json",
                True,
                MUTED,
            ),
            (20, 48),
        )

        pygame.draw.rect(screen, PLAY_BG, PLAY_AREA, border_radius=8)
        pygame.draw.rect(screen, (50, 58, 76), PLAY_AREA, width=2, border_radius=8)
        pygame.draw.rect(screen, PANEL_BG, PANEL, border_radius=8)
        pygame.draw.rect(screen, (50, 58, 76), PANEL, width=2, border_radius=8)

        screen.blit(
            body_font.render("Save slots", True, TEXT),
            (PANEL.left + 20, PANEL.top + 16),
        )

        for index in range(SLOT_COUNT):
            slot = index + 1
            row_y = PANEL.top + 56 + index * 120
            filled = slot_has_file(slot)
            badge = "file present" if filled else "empty"
            badge_color = OK if filled else MUTED
            screen.blit(
                body_font.render(f"Slot {slot}", True, TEXT),
                (PANEL.left + 20, row_y),
            )
            screen.blit(
                small_font.render(f"{slot_path(slot)}  ({badge})", True, badge_color),
                (PANEL.left + 20, row_y + 22),
            )

        for button in buttons:
            draw_button(screen, button, body_font, hover=button.hit(mouse))

        for name, rect in boxes.items():
            color = BOX_COLORS[name]
            pygame.draw.rect(screen, color, rect, border_radius=8)
            if dragging == name:
                pygame.draw.rect(screen, TEXT, rect, width=3, border_radius=8)
            else:
                pygame.draw.rect(screen, (10, 12, 16), rect, width=2, border_radius=8)
            label = small_font.render(name[0].upper(), True, TEXT)
            screen.blit(label, label.get_rect(center=rect.center))

        screen.blit(
            small_font.render(status, True, status_color),
            (20, SCREEN_HEIGHT - 28),
        )

        fps_text = small_font.render(f"FPS: {clock.get_fps():.0f}", True, MUTED)
        screen.blit(fps_text, (SCREEN_WIDTH - fps_text.get_width() - 20, 22))

        pygame.display.flip()
        await asyncio.sleep(1 / (60 * 2))


if __name__ == "__main__":
    asyncio.run(main())

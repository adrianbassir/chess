"""
main.py — Entry point for the pygame chess application.

Run with:
    python main.py

Dependencies:
    pip install pygame

To package as a standalone .exe:
    pip install pyinstaller
    pyinstaller --onefile --noconsole main.py
"""

import sys
import pygame
from game import Game
from board import BoardRenderer, BOARD_OFFSET_X, BOARD_OFFSET_Y, SQUARE_SIZE

# ---------------------------------------------------------------------------
# Window geometry
# ---------------------------------------------------------------------------

WINDOW_W = BOARD_OFFSET_X * 2 + SQUARE_SIZE * 8   # 720
WINDOW_H = BOARD_OFFSET_Y + SQUARE_SIZE * 8 + 36  # 732
FPS = 60
WINDOW_TITLE = "Chess"


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    pygame.init()

    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption(WINDOW_TITLE)

    # Set a simple chess-piece icon (pawn silhouette using a surface)
    icon = pygame.Surface((32, 32), pygame.SRCALPHA)
    icon.fill((0, 0, 0, 0))
    pygame.draw.circle(icon, (220, 220, 220), (16, 10), 7)
    pygame.draw.rect(icon, (220, 220, 220), pygame.Rect(11, 16, 10, 10))
    pygame.draw.rect(icon, (220, 220, 220), pygame.Rect(8,  26, 16, 4))
    pygame.display.set_icon(icon)

    clock    = pygame.time.Clock()
    game     = Game()
    renderer = BoardRenderer(screen)

    running = True
    while running:
        # ----------------------------------------------------------------
        # Event handling
        # ----------------------------------------------------------------
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    # R — restart the game
                    game.reset()

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = pygame.mouse.get_pos()

                if game.promotion_pending:
                    # The promotion overlay is active — route clicks to it
                    chosen = renderer.get_promotion_click(game, (mx, my))
                    if chosen is not None:
                        game.promote_pawn(chosen)
                else:
                    # Normal play — map pixel to board square
                    sq = renderer.pixel_to_square(mx, my)
                    if sq is not None:
                        game.select_square(*sq)

        # ----------------------------------------------------------------
        # Render
        # ----------------------------------------------------------------
        renderer.draw_board(game)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == '__main__':
    main()

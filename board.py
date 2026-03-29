"""
board.py — Board and piece rendering via pygame.

Responsibilities:
  - Draw the 8×8 board with alternating light/dark squares
  - Overlay highlights: selected square, legal-move dots/rings, last-move tint,
    king-in-check red flash
  - Render piece glyphs using Unicode chess symbols via system font
  - Draw board coordinates (files a–h, ranks 1–8)
  - Draw the promotion selection overlay
  - Translate pixel coordinates → board square

All colours and dimensions live as module-level constants so a theme or
resolution change requires touching only this file.
"""

import pygame
from pieces import King, Queen, Rook, Bishop, Knight, Pawn

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

SQUARE_SIZE    = 80          # Pixels per square
BOARD_OFFSET_X = 40          # Left margin (for rank numbers + breathing room)
BOARD_OFFSET_Y = 56          # Top margin (for status bar)
COORD_MARGIN   = 18          # Extra space inside board edge for coordinate labels

# Window size is derived from these in main.py:
#   width  = BOARD_OFFSET_X * 2 + SQUARE_SIZE * 8
#   height = BOARD_OFFSET_Y + SQUARE_SIZE * 8 + 36

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

C_LIGHT       = (240, 217, 181)   # Light square
C_DARK        = (181, 136,  99)   # Dark square
C_BACKGROUND  = ( 22,  21,  18)   # Window background
C_SELECTED    = (130, 151, 105)   # Selected-square tint
C_LAST_MOVE   = (205, 210, 106)   # Last-move tint
C_LEGAL_DOT   = (100, 111,  64)   # Legal-move dot / ring
C_CHECK       = (220,  50,  50)   # King-in-check flash
C_PROMO_BG    = ( 40,  40,  40)
C_PROMO_HOVER = ( 80,  80,  80)
C_PROMO_BORD  = ( 70,  70,  70)
C_UI_LIGHT    = (240, 240, 240)
C_UI_DARK     = (160, 160, 160)
C_UI_GOLD     = (255, 215,   0)
C_UI_DIM      = (100, 100, 100)

# Alpha values (0–255) for surface overlays
A_SELECTED    = 150
A_LAST_MOVE   = 120
A_CHECK       = 160
A_LEGAL_DOT   = 185
A_OVERLAY     = 160   # Promotion dim overlay

# ---------------------------------------------------------------------------
# Piece font candidates (Windows first, then cross-platform fallbacks)
# ---------------------------------------------------------------------------

_PIECE_FONT_CANDIDATES = [
    'segoeuisymbol', 'seguisym', 'segoeui',
    'dejavusans', 'freesans', 'notosans',
    'symbola', 'unifont',
]
_PIECE_FONT_SIZE   = 56
_UI_FONT_SIZE      = 22
_STATUS_FONT_SIZE  = 30
_COORD_FONT_SIZE   = 13
_PROMO_FONT_SIZE   = 54

# Test glyph — if this renders with a non-trivial width the font is usable
_TEST_GLYPH = '♔'


# ---------------------------------------------------------------------------
# BoardRenderer
# ---------------------------------------------------------------------------

class BoardRenderer:
    """Renders the full board, pieces, and UI elements to a pygame Surface."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self._load_fonts()

    # ------------------------------------------------------------------
    # Font loading
    # ------------------------------------------------------------------

    def _load_fonts(self):
        """Load the best available system font for chess glyphs."""
        self.piece_font = None
        for name in _PIECE_FONT_CANDIDATES:
            try:
                f = pygame.font.SysFont(name, _PIECE_FONT_SIZE)
                w = f.render(_TEST_GLYPH, True, (0, 0, 0)).get_width()
                if w > 8:
                    self.piece_font = f
                    break
            except Exception:
                continue

        if self.piece_font is None:
            # Last resort: pygame's built-in bitmap font (won't have chess glyphs
            # but avoids a crash — pieces will appear as '?' boxes)
            self.piece_font = pygame.font.Font(None, _PIECE_FONT_SIZE)

        self.ui_font     = pygame.font.SysFont('arial', _UI_FONT_SIZE)
        self.status_font = pygame.font.SysFont('arial', _STATUS_FONT_SIZE, bold=True)
        self.coord_font  = pygame.font.SysFont('arial', _COORD_FONT_SIZE)

        # Promotion menu uses a larger glyph
        self.promo_font  = self.piece_font  # Reuse piece font at construction size

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def square_rect(self, row: int, col: int) -> pygame.Rect:
        """Return the pygame.Rect for the given board square."""
        x = BOARD_OFFSET_X + col * SQUARE_SIZE
        y = BOARD_OFFSET_Y + row * SQUARE_SIZE
        return pygame.Rect(x, y, SQUARE_SIZE, SQUARE_SIZE)

    def pixel_to_square(self, px: int, py: int):
        """
        Convert a pixel coordinate to a (row, col) tuple.
        Returns None if the pixel is outside the board.
        """
        col = (px - BOARD_OFFSET_X) // SQUARE_SIZE
        row = (py - BOARD_OFFSET_Y) // SQUARE_SIZE
        if 0 <= row < 8 and 0 <= col < 8:
            return (row, col)
        return None

    # ------------------------------------------------------------------
    # Main draw entry point
    # ------------------------------------------------------------------

    def draw_board(self, game):
        """Full redraw: background → squares → pieces → UI → optional promotion."""
        self.screen.fill(C_BACKGROUND)
        self._draw_squares(game)
        self._draw_coordinates()
        self._draw_pieces(game)
        self._draw_ui(game)
        if game.promotion_pending:
            self._draw_promotion_overlay(game)

    # ------------------------------------------------------------------
    # Squares and overlays
    # ------------------------------------------------------------------

    def _draw_squares(self, game):
        """Draw base squares and all highlight layers."""
        # Find king position if in check (for red flash)
        check_king = None
        if game.state.status == 'playing' and game.current_player_in_check():
            for r in range(8):
                for c in range(8):
                    p = game.board[r][c]
                    if isinstance(p, King) and p.color == game.state.current_turn:
                        check_king = (r, c)
                        break

        for row in range(8):
            for col in range(8):
                rect = self.square_rect(row, col)
                light = (row + col) % 2 == 0
                pygame.draw.rect(self.screen, C_LIGHT if light else C_DARK, rect)

                # Last-move tint (both from and to squares)
                if game.last_move and (row, col) in game.last_move:
                    self._blit_alpha(rect, C_LAST_MOVE, A_LAST_MOVE)

                # Selected-square tint
                if (game.selected_piece
                        and game.selected_piece.row == row
                        and game.selected_piece.col == col):
                    self._blit_alpha(rect, C_SELECTED, A_SELECTED)

                # King-in-check flash
                if check_king == (row, col):
                    self._blit_alpha(rect, C_CHECK, A_CHECK)

                # Legal-move indicators
                if (row, col) in game.legal_moves:
                    if game.board[row][col] is not None:
                        # Capture: hollow ring around the piece
                        surf = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
                        pygame.draw.circle(
                            surf, (*C_LEGAL_DOT, A_LEGAL_DOT),
                            (SQUARE_SIZE // 2, SQUARE_SIZE // 2),
                            SQUARE_SIZE // 2 - 4, 6
                        )
                        self.screen.blit(surf, rect)
                    else:
                        # Empty square: small filled dot
                        surf = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
                        pygame.draw.circle(
                            surf, (*C_LEGAL_DOT, A_LEGAL_DOT),
                            (SQUARE_SIZE // 2, SQUARE_SIZE // 2),
                            SQUARE_SIZE // 7
                        )
                        self.screen.blit(surf, rect)

    def _blit_alpha(self, rect: pygame.Rect, color: tuple, alpha: int):
        """Blit a solid-colour alpha overlay onto *rect*."""
        surf = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
        surf.fill((*color, alpha))
        self.screen.blit(surf, rect)

    # ------------------------------------------------------------------
    # Coordinates
    # ------------------------------------------------------------------

    def _draw_coordinates(self):
        """Draw rank numbers (1–8) on the left and file letters (a–h) at the bottom."""
        files = 'abcdefgh'
        ranks = '87654321'   # Row 0 is rank 8

        for i in range(8):
            # File letter — bottom-right corner of each square in the last row
            is_light_square = (7 + i) % 2 == 0
            fg = C_DARK if is_light_square else C_LIGHT
            f_surf = self.coord_font.render(files[i], True, fg)
            fx = BOARD_OFFSET_X + i * SQUARE_SIZE + SQUARE_SIZE - f_surf.get_width() - 3
            fy = BOARD_OFFSET_Y + 8 * SQUARE_SIZE - f_surf.get_height() - 2
            self.screen.blit(f_surf, (fx, fy))

            # Rank number — top-left corner of each square in the first column
            is_light_square = (i + 0) % 2 == 0
            fg = C_DARK if is_light_square else C_LIGHT
            r_surf = self.coord_font.render(ranks[i], True, fg)
            rx = BOARD_OFFSET_X + 3
            ry = BOARD_OFFSET_Y + i * SQUARE_SIZE + 3
            self.screen.blit(r_surf, (rx, ry))

    # ------------------------------------------------------------------
    # Piece rendering
    # ------------------------------------------------------------------

    def _draw_pieces(self, game):
        for row in range(8):
            for col in range(8):
                piece = game.board[row][col]
                if piece is not None:
                    self._draw_piece(piece)

    def _draw_piece(self, piece):
        """
        Draw a chess piece glyph centred on its square.

        Uses outline-stroke technique (render shadow slightly offset in all
        8 directions) so glyphs are visible on both light and dark squares.
        """
        rect = self.square_rect(piece.row, piece.col)
        glyph = piece.unicode_symbol()

        fg     = (255, 255, 255) if piece.color == 'white' else ( 15,  15,  15)
        shadow = ( 15,  15,  15) if piece.color == 'white' else (210, 210, 210)

        main_surf   = self.piece_font.render(glyph, True, fg)
        shadow_surf = self.piece_font.render(glyph, True, shadow)

        cx = rect.x + (SQUARE_SIZE - main_surf.get_width())  // 2
        cy = rect.y + (SQUARE_SIZE - main_surf.get_height()) // 2

        # 8-direction outline for contrast
        for dx, dy in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)):
            self.screen.blit(shadow_surf, (cx + dx, cy + dy))

        self.screen.blit(main_surf, (cx, cy))

    # ------------------------------------------------------------------
    # UI bar (status, turn, hints)
    # ------------------------------------------------------------------

    def _draw_ui(self, game):
        board_w = 8 * SQUARE_SIZE

        if game.state.status == 'playing':
            turn_str = "White's Turn" if game.state.current_turn == 'white' else "Black's Turn"
            if game.current_player_in_check():
                turn_str += "  —  CHECK!"
            fg = C_UI_LIGHT if game.state.current_turn == 'white' else C_UI_DARK
            surf = self.ui_font.render(turn_str, True, fg)
        else:
            if game.state.status == 'checkmate':
                winner = game.state.winner.capitalize()
                msg = f"Checkmate!  {winner} wins."
            elif game.state.status == 'stalemate':
                msg = "Stalemate — Draw"
            else:
                msg = "Draw"
            surf = self.status_font.render(msg, True, C_UI_GOLD)

        # Vertically centre in the top margin
        sy = (BOARD_OFFSET_Y - surf.get_height()) // 2
        self.screen.blit(surf, (BOARD_OFFSET_X, sy))

        # Move counter — bottom left
        move_surf = self.coord_font.render(
            f"Move {game.state.full_move_number}", True, C_UI_DIM)
        self.screen.blit(move_surf, (
            BOARD_OFFSET_X,
            BOARD_OFFSET_Y + board_w + 6
        ))

        # Restart hint — bottom right
        hint = self.coord_font.render("R — restart", True, C_UI_DIM)
        self.screen.blit(hint, (
            BOARD_OFFSET_X + board_w - hint.get_width(),
            BOARD_OFFSET_Y + board_w + 6
        ))

    # ------------------------------------------------------------------
    # Promotion overlay
    # ------------------------------------------------------------------

    def _draw_promotion_overlay(self, game):
        """
        Draw a centred promotion-choice panel with Queen / Rook / Bishop / Knight.
        Also shows a title above the panel.
        """
        _, _, color = game.promotion_pending
        choices = [Queen, Rook, Bishop, Knight]
        syms = {
            'white': ['♕', '♖', '♗', '♘'],
            'black': ['♛', '♜', '♝', '♞'],
        }

        panel_w = 4 * SQUARE_SIZE
        panel_h = SQUARE_SIZE + 16
        panel_x = BOARD_OFFSET_X + (8 * SQUARE_SIZE - panel_w) // 2
        panel_y = BOARD_OFFSET_Y + (8 * SQUARE_SIZE - panel_h) // 2

        # Dim the rest of the board
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, A_OVERLAY))
        self.screen.blit(overlay, (0, 0))

        # Panel background
        border_rect = pygame.Rect(panel_x - 6, panel_y - 32, panel_w + 12, panel_h + 38)
        pygame.draw.rect(self.screen, C_PROMO_BORD, border_rect, border_radius=8)
        pygame.draw.rect(self.screen, C_PROMO_BG,
                         pygame.Rect(panel_x, panel_y, panel_w, panel_h), border_radius=6)

        # Title
        title = self.ui_font.render("Promote to:", True, (210, 210, 210))
        self.screen.blit(title, (panel_x + (panel_w - title.get_width()) // 2, panel_y - 26))

        mouse_pos = pygame.mouse.get_pos()
        for i, (sym, _cls) in enumerate(zip(syms[color], choices)):
            box = pygame.Rect(panel_x + i * SQUARE_SIZE, panel_y + 8, SQUARE_SIZE, SQUARE_SIZE)
            if box.collidepoint(mouse_pos):
                pygame.draw.rect(self.screen, C_PROMO_HOVER, box, border_radius=4)

            fg     = (255, 255, 255) if color == 'white' else ( 15,  15,  15)
            shadow = ( 15,  15,  15) if color == 'white' else (210, 210, 210)

            main_s   = self.piece_font.render(sym, True, fg)
            shadow_s = self.piece_font.render(sym, True, shadow)
            gx = box.x + (SQUARE_SIZE - main_s.get_width())  // 2
            gy = box.y + (SQUARE_SIZE - main_s.get_height()) // 2
            for dx, dy in ((-1,-1),(-1,1),(1,-1),(1,1)):
                self.screen.blit(shadow_s, (gx + dx, gy + dy))
            self.screen.blit(main_s, (gx, gy))

    def get_promotion_click(self, game, mouse_pos) -> type | None:
        """
        If mouse_pos falls on a promotion panel option, return the piece class.
        Returns None if the click is outside the panel.
        """
        if not game.promotion_pending:
            return None

        choices = [Queen, Rook, Bishop, Knight]
        panel_w = 4 * SQUARE_SIZE
        panel_h = SQUARE_SIZE + 16
        panel_x = BOARD_OFFSET_X + (8 * SQUARE_SIZE - panel_w) // 2
        panel_y = BOARD_OFFSET_Y + (8 * SQUARE_SIZE - panel_h) // 2

        for i, cls in enumerate(choices):
            box = pygame.Rect(panel_x + i * SQUARE_SIZE, panel_y + 8, SQUARE_SIZE, SQUARE_SIZE)
            if box.collidepoint(mouse_pos):
                return cls
        return None

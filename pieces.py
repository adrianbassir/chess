"""
pieces.py — Chess piece classes.

Each piece knows its color, position, and how to generate pseudo-legal moves
(moves ignoring whether they leave the king in check). Legal move filtering
happens in rules.py.

Designed for extensibility: pieces carry enough state for AI evaluation,
PGN export, and self-play training.
"""


class Piece:
    """Abstract base class for all chess pieces."""

    def __init__(self, color: str, row: int, col: int):
        self.color = color        # 'white' or 'black'
        self.row = row
        self.col = col
        self.has_moved = False    # Tracks first move (castling, pawn double-push)

    # ------------------------------------------------------------------
    # Subclasses must implement these
    # ------------------------------------------------------------------

    def get_pseudo_legal_moves(self, board, game_state) -> list:
        """
        Return list of (row, col) squares this piece can move to,
        ignoring whether the move leaves own king in check.
        """
        raise NotImplementedError

    def symbol(self) -> str:
        """Single-character FEN symbol (uppercase = white, lowercase = black)."""
        raise NotImplementedError

    def unicode_symbol(self) -> str:
        """Unicode chess glyph for display."""
        raise NotImplementedError

    def copy(self):
        """Deep-copy the piece (for move simulation in rules.py)."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Helpers shared by sliding pieces
    # ------------------------------------------------------------------

    def _slide(self, board, directions) -> list:
        """Slide along a list of (dr, dc) direction vectors until blocked."""
        moves = []
        for dr, dc in directions:
            nr, nc = self.row + dr, self.col + dc
            while 0 <= nr < 8 and 0 <= nc < 8:
                target = board[nr][nc]
                if target is None:
                    moves.append((nr, nc))
                elif target.color != self.color:
                    moves.append((nr, nc))   # Capture — then stop
                    break
                else:
                    break                    # Blocked by own piece
                nr += dr
                nc += dc
        return moves

    def __repr__(self):
        return f"{type(self).__name__}({self.color},{self.row},{self.col})"


# ---------------------------------------------------------------------------
# Concrete piece classes
# ---------------------------------------------------------------------------

class Pawn(Piece):

    def get_pseudo_legal_moves(self, board, game_state) -> list:
        moves = []
        # White advances up the board (decreasing row index).
        # Black advances down (increasing row index).
        direction = -1 if self.color == 'white' else 1
        start_row = 6 if self.color == 'white' else 1

        r, c = self.row, self.col

        # --- Forward one square ---
        nr = r + direction
        if 0 <= nr < 8 and board[nr][c] is None:
            moves.append((nr, c))

            # --- Forward two squares (only from starting row) ---
            if r == start_row and board[r + 2 * direction][c] is None:
                moves.append((r + 2 * direction, c))

        # --- Diagonal captures ---
        for dc in (-1, 1):
            nc = c + dc
            nr = r + direction
            if not (0 <= nr < 8 and 0 <= nc < 8):
                continue
            target = board[nr][nc]
            if target is not None and target.color != self.color:
                moves.append((nr, nc))
            # En passant: game_state records the square a pawn skipped over
            elif game_state.en_passant_target == (nr, nc):
                moves.append((nr, nc))

        return moves

    def symbol(self):
        return 'P' if self.color == 'white' else 'p'

    def unicode_symbol(self):
        return '♙' if self.color == 'white' else '♟'

    def copy(self):
        p = Pawn(self.color, self.row, self.col)
        p.has_moved = self.has_moved
        return p


class Rook(Piece):

    def get_pseudo_legal_moves(self, board, game_state) -> list:
        return self._slide(board, [(0, 1), (0, -1), (1, 0), (-1, 0)])

    def symbol(self):
        return 'R' if self.color == 'white' else 'r'

    def unicode_symbol(self):
        return '♖' if self.color == 'white' else '♜'

    def copy(self):
        p = Rook(self.color, self.row, self.col)
        p.has_moved = self.has_moved
        return p


class Knight(Piece):

    _JUMPS = [(-2, -1), (-2, 1), (-1, -2), (-1, 2),
              (1, -2),  (1, 2),  (2, -1),  (2, 1)]

    def get_pseudo_legal_moves(self, board, game_state) -> list:
        moves = []
        for dr, dc in self._JUMPS:
            nr, nc = self.row + dr, self.col + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                target = board[nr][nc]
                if target is None or target.color != self.color:
                    moves.append((nr, nc))
        return moves

    def symbol(self):
        return 'N' if self.color == 'white' else 'n'

    def unicode_symbol(self):
        return '♘' if self.color == 'white' else '♞'

    def copy(self):
        p = Knight(self.color, self.row, self.col)
        p.has_moved = self.has_moved
        return p


class Bishop(Piece):

    def get_pseudo_legal_moves(self, board, game_state) -> list:
        return self._slide(board, [(1, 1), (1, -1), (-1, 1), (-1, -1)])

    def symbol(self):
        return 'B' if self.color == 'white' else 'b'

    def unicode_symbol(self):
        return '♗' if self.color == 'white' else '♝'

    def copy(self):
        p = Bishop(self.color, self.row, self.col)
        p.has_moved = self.has_moved
        return p


class Queen(Piece):

    def get_pseudo_legal_moves(self, board, game_state) -> list:
        return self._slide(board, [
            (0, 1), (0, -1), (1, 0), (-1, 0),
            (1, 1), (1, -1), (-1, 1), (-1, -1)
        ])

    def symbol(self):
        return 'Q' if self.color == 'white' else 'q'

    def unicode_symbol(self):
        return '♕' if self.color == 'white' else '♛'

    def copy(self):
        p = Queen(self.color, self.row, self.col)
        p.has_moved = self.has_moved
        return p


class King(Piece):

    def get_pseudo_legal_moves(self, board, game_state) -> list:
        moves = []
        r, c = self.row, self.col

        # Standard king moves — one square in any direction
        for dr, dc in [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                target = board[nr][nc]
                if target is None or target.color != self.color:
                    moves.append((nr, nc))

        # --- Castling (square-occupancy check only; check-path tested in rules.py) ---
        if not self.has_moved:
            # Kingside: squares f and g must be empty, rook on h must not have moved
            rook_ks = board[r][7]
            if (isinstance(rook_ks, Rook) and rook_ks.color == self.color
                    and not rook_ks.has_moved
                    and board[r][5] is None
                    and board[r][6] is None):
                moves.append((r, 6))

            # Queenside: squares b, c, d must be empty, rook on a must not have moved
            rook_qs = board[r][0]
            if (isinstance(rook_qs, Rook) and rook_qs.color == self.color
                    and not rook_qs.has_moved
                    and board[r][1] is None
                    and board[r][2] is None
                    and board[r][3] is None):
                moves.append((r, 2))

        return moves

    def symbol(self):
        return 'K' if self.color == 'white' else 'k'

    def unicode_symbol(self):
        return '♔' if self.color == 'white' else '♚'

    def copy(self):
        p = King(self.color, self.row, self.col)
        p.has_moved = self.has_moved
        return p

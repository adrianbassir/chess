"""
game.py — Game state management and move execution.

GameState holds all data needed to fully describe a chess position:
  - board (8×8 grid of Piece | None)
  - current turn
  - en-passant target square
  - move history (list of dicts — ready for PGN export or AI training)
  - half-move clock (50-move rule)
  - full-move number

Game drives player interaction:
  - select_square() handles click → select / move / deselect logic
  - _make_move() applies a fully validated move
  - promote_pawn() completes a pending promotion
  - reset() returns to the starting position

The Game class intentionally exposes enough state for an AI layer to read
positions, enumerate legal moves, and inject moves without owning a UI.
"""

from pieces import Pawn, Rook, Knight, Bishop, Queen, King
from rules import get_legal_moves, is_in_check, is_checkmate, is_stalemate, is_insufficient_material


class GameState:
    """All mutable state that describes the current chess position."""

    def __init__(self):
        self.current_turn: str = 'white'
        self.en_passant_target = None       # (row, col) or None
        self.half_move_clock: int = 0       # Resets on pawn move or capture
        self.full_move_number: int = 1      # Increments after Black's move
        self.status: str = 'playing'        # 'playing' | 'checkmate' | 'stalemate' | 'draw'
        self.winner = None                  # 'white' | 'black' | None
        # --- Move history ---
        # Each entry is a dict with keys:
        #   piece, color, from, to, capture, en_passant, castling, promotion, check, checkmate
        # Structured for easy PGN serialisation and AI training replay.
        self.move_history: list = []


class Game:
    """Top-level game controller — owns the board and handles all move logic."""

    def __init__(self):
        self.board = self._make_starting_board()
        self.state = GameState()
        self.selected_piece = None   # Currently highlighted piece (or None)
        self.legal_moves: list = []  # Legal destinations for selected_piece
        # Set to (row, col, color) when a pawn reaches the promotion rank;
        # the game pauses until promote_pawn() is called.
        self.promotion_pending = None
        # Track last move for UI highlighting
        self.last_move = None        # ((from_row, from_col), (to_row, to_col)) or None

    # ------------------------------------------------------------------
    # Board initialisation
    # ------------------------------------------------------------------

    @staticmethod
    def _make_starting_board():
        board = [[None] * 8 for _ in range(8)]
        back_rank = [Rook, Knight, Bishop, Queen, King, Bishop, Knight, Rook]

        # Black back rank — row 0
        for col, cls in enumerate(back_rank):
            board[0][col] = cls('black', 0, col)
        # Black pawns — row 1
        for col in range(8):
            board[1][col] = Pawn('black', 1, col)

        # White back rank — row 7
        for col, cls in enumerate(back_rank):
            board[7][col] = cls('white', 7, col)
        # White pawns — row 6
        for col in range(8):
            board[6][col] = Pawn('white', 6, col)

        return board

    # ------------------------------------------------------------------
    # Player interaction
    # ------------------------------------------------------------------

    def select_square(self, row: int, col: int) -> bool:
        """
        Handle a board-square click.

        Returns True if a move was executed, False otherwise.
        Ignores clicks when the game is over or a promotion is pending.
        """
        if self.state.status != 'playing' or self.promotion_pending:
            return False

        piece = self.board[row][col]

        if self.selected_piece is not None:
            # --- Attempt to move to the clicked square ---
            if (row, col) in self.legal_moves:
                self._make_move(self.selected_piece, row, col)
                self.selected_piece = None
                self.legal_moves = []
                return True

            # --- Re-select a different piece of the same colour ---
            if piece is not None and piece.color == self.state.current_turn:
                self.selected_piece = piece
                self.legal_moves = get_legal_moves(piece, self.board, self.state)
                return False

            # --- Click on empty square or enemy — deselect ---
            self.selected_piece = None
            self.legal_moves = []
            return False

        # --- No piece selected yet: select one ---
        if piece is not None and piece.color == self.state.current_turn:
            self.selected_piece = piece
            self.legal_moves = get_legal_moves(piece, self.board, self.state)

        return False

    # ------------------------------------------------------------------
    # Move execution
    # ------------------------------------------------------------------

    def _make_move(self, piece, to_row: int, to_col: int):
        """
        Execute a pre-validated move and update all game state.

        Handles: en passant, castling, promotion detection, castling-rights
        updates, half-move clock, full-move number, and game-over detection.
        """
        from_row, from_col = piece.row, piece.col

        # Build the history record before the board changes
        record = {
            'piece':      type(piece).__name__,
            'color':      piece.color,
            'from':       (from_row, from_col),
            'to':         (to_row, to_col),
            'capture':    self.board[to_row][to_col] is not None,
            'en_passant': False,
            'castling':   None,   # 'kingside' | 'queenside' | None
            'promotion':  None,   # piece symbol after promotion, or None
            'check':      False,
            'checkmate':  False,
        }

        # --- En passant capture ---
        if (isinstance(piece, Pawn)
                and self.state.en_passant_target == (to_row, to_col)):
            # The captured pawn sits on from_row, not to_row
            self.board[from_row][to_col] = None
            record['en_passant'] = True
            record['capture'] = True

        # --- Castling: relocate the rook ---
        if isinstance(piece, King) and abs(to_col - from_col) == 2:
            if to_col == 6:   # Kingside
                rook = self.board[from_row][7]
                self.board[from_row][5] = rook
                self.board[from_row][7] = None
                if rook:
                    rook.col = 5
                    rook.has_moved = True
                record['castling'] = 'kingside'
            else:             # Queenside
                rook = self.board[from_row][0]
                self.board[from_row][3] = rook
                self.board[from_row][0] = None
                if rook:
                    rook.col = 3
                    rook.has_moved = True
                record['castling'] = 'queenside'

        # --- Update castling rights ---
        if isinstance(piece, King):
            # King move forfeits both castling rights for this colour
            pass  # Rights are tracked via has_moved on King / Rooks
        if isinstance(piece, Rook):
            pass  # Same — tracked via has_moved

        # --- Apply the move ---
        self.board[to_row][to_col] = piece
        self.board[from_row][from_col] = None
        piece.row = to_row
        piece.col = to_col
        piece.has_moved = True

        # --- En-passant target for the resulting position ---
        if isinstance(piece, Pawn) and abs(to_row - from_row) == 2:
            ep_row = (from_row + to_row) // 2
            self.state.en_passant_target = (ep_row, to_col)
        else:
            self.state.en_passant_target = None

        # --- Half-move clock (50-move rule) ---
        if isinstance(piece, Pawn) or record['capture']:
            self.state.half_move_clock = 0
        else:
            self.state.half_move_clock += 1

        # --- Full-move number (increments after Black's move) ---
        if piece.color == 'black':
            self.state.full_move_number += 1

        # --- Record last move for UI ---
        self.last_move = ((from_row, from_col), (to_row, to_col))

        # --- Pawn promotion check ---
        if isinstance(piece, Pawn):
            if (piece.color == 'white' and to_row == 0) or \
               (piece.color == 'black' and to_row == 7):
                self.promotion_pending = (to_row, to_col, piece.color)
                # History entry completed after promotion choice
                self.state.move_history.append(record)
                return   # Do NOT switch turn until promotion is resolved

        self.state.move_history.append(record)
        self._post_move_checks(record)

    def _post_move_checks(self, record=None):
        """Switch turn and evaluate game-ending conditions."""
        opponent = 'black' if self.state.current_turn == 'white' else 'white'
        self.state.current_turn = opponent

        if is_checkmate(opponent, self.board, self.state):
            self.state.status = 'checkmate'
            self.state.winner = 'white' if opponent == 'black' else 'black'
            if record:
                record['checkmate'] = True
        elif is_stalemate(opponent, self.board, self.state):
            self.state.status = 'stalemate'
        elif self.state.half_move_clock >= 100:
            self.state.status = 'draw'
        elif is_insufficient_material(self.board):
            self.state.status = 'draw'
        else:
            # Tag the record if the opponent is now in check
            if record and is_in_check(self.board, opponent, self.state):
                record['check'] = True

    # ------------------------------------------------------------------
    # Pawn promotion
    # ------------------------------------------------------------------

    def promote_pawn(self, piece_class):
        """
        Replace the promoting pawn with the chosen piece class.
        piece_class should be one of: Queen, Rook, Bishop, Knight.
        """
        if not self.promotion_pending:
            return
        row, col, color = self.promotion_pending
        new_piece = piece_class(color, row, col)
        new_piece.has_moved = True
        self.board[row][col] = new_piece
        self.promotion_pending = None
        # Update the last history entry with the promotion symbol
        if self.state.move_history:
            self.state.move_history[-1]['promotion'] = new_piece.symbol().upper()
        self._post_move_checks()

    # ------------------------------------------------------------------
    # Public helpers (useful for AI / training layer)
    # ------------------------------------------------------------------

    def reset(self):
        """Return to the initial position."""
        self.board = self._make_starting_board()
        self.state = GameState()
        self.selected_piece = None
        self.legal_moves = []
        self.promotion_pending = None
        self.last_move = None

    def current_player_in_check(self) -> bool:
        return is_in_check(self.board, self.state.current_turn, self.state)

    def get_all_legal_moves(self, color: str) -> dict:
        """
        Return {piece: [(row, col), ...]} for every piece of *color*.
        Useful for AI enumeration.
        """
        result = {}
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p is not None and p.color == color:
                    moves = get_legal_moves(p, self.board, self.state)
                    if moves:
                        result[p] = moves
        return result

    def get_move_history(self) -> list:
        """Return the full annotated move history (for PGN export, replay, training)."""
        return self.state.move_history

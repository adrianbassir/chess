"""
rules.py — Legal move enforcement, check / checkmate / stalemate detection.

Key design notes:
  * get_legal_moves() filters pseudo-legal moves by simulating each move on a
    temporary board and verifying the king is not left in check.
  * apply_move_to_board() is purely functional: it never modifies the real board.
  * Castling requires the king to not be in check, not pass through a checked
    square, and not land on a checked square — all verified here.
  * is_in_check() only calls get_pseudo_legal_moves() (not get_legal_moves())
    to avoid infinite recursion.
"""

from pieces import King, Rook, Pawn


# ---------------------------------------------------------------------------
# Minimal game-state stand-in for check-detection during move simulation
# ---------------------------------------------------------------------------

class _SimState:
    """Lightweight game-state used when simulating positions for check detection."""
    def __init__(self, en_passant_target=None):
        self.en_passant_target = en_passant_target


# ---------------------------------------------------------------------------
# Board copy helper
# ---------------------------------------------------------------------------

def _copy_board(board):
    """Return a fully independent copy of the 8×8 board (pieces are deep-copied)."""
    new_board = [[None] * 8 for _ in range(8)]
    for r in range(8):
        for c in range(8):
            if board[r][c] is not None:
                new_board[r][c] = board[r][c].copy()
    return new_board


# ---------------------------------------------------------------------------
# Low-level move application (used for legal-move simulation only)
# ---------------------------------------------------------------------------

def apply_move_to_board(board, piece, to_row, to_col, game_state):
    """
    Apply a single move to a *copy* of board.  Handles special moves:
      - En passant capture
      - Castling (moves the rook as well)
      - Pawn two-square advance (sets new en-passant target)

    Returns:
        (new_board, new_ep_target) — the resulting board and en-passant square.
    """
    new_board = _copy_board(board)
    from_row, from_col = piece.row, piece.col
    moving = new_board[from_row][from_col]   # The copied piece we're moving

    new_ep_target = None

    # --- En passant: the captured pawn sits on the same rank as the moving pawn ---
    if (isinstance(moving, Pawn)
            and game_state.en_passant_target == (to_row, to_col)):
        # The captured pawn is on from_row, to_col (not to_row)
        new_board[from_row][to_col] = None

    # --- Castling: move the rook to its new square ---
    if isinstance(moving, King) and abs(to_col - from_col) == 2:
        if to_col == 6:   # Kingside
            rook = new_board[from_row][7]
            new_board[from_row][5] = rook
            new_board[from_row][7] = None
            if rook:
                rook.col = 5
                rook.has_moved = True
        else:             # Queenside (to_col == 2)
            rook = new_board[from_row][0]
            new_board[from_row][3] = rook
            new_board[from_row][0] = None
            if rook:
                rook.col = 3
                rook.has_moved = True

    # --- Move the piece ---
    new_board[to_row][to_col] = moving
    new_board[from_row][from_col] = None
    moving.row = to_row
    moving.col = to_col
    moving.has_moved = True

    # --- Record en-passant target for the resulting position ---
    if isinstance(moving, Pawn) and abs(to_row - from_row) == 2:
        ep_row = (from_row + to_row) // 2
        new_ep_target = (ep_row, to_col)

    return new_board, new_ep_target


# ---------------------------------------------------------------------------
# Check detection
# ---------------------------------------------------------------------------

def is_in_check(board, color, game_state) -> bool:
    """
    Return True if *color*'s king is under attack in *board*.

    Uses pseudo-legal moves only (no recursion into legal-move filtering).
    """
    # Locate the king
    king_pos = None
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if isinstance(p, King) and p.color == color:
                king_pos = (r, c)
                break
        if king_pos:
            break

    if king_pos is None:
        return False   # Should never happen in a valid game

    opponent = 'black' if color == 'white' else 'white'
    # Pass a neutral sim-state so opponent pawns don't use stale en-passant data
    sim = _SimState(game_state.en_passant_target if game_state else None)

    for r in range(8):
        for c in range(8):
            attacker = board[r][c]
            if attacker is not None and attacker.color == opponent:
                if king_pos in attacker.get_pseudo_legal_moves(board, sim):
                    return True
    return False


# ---------------------------------------------------------------------------
# Legal move generation
# ---------------------------------------------------------------------------

def get_legal_moves(piece, board, game_state) -> list:
    """
    Return all fully legal moves for *piece* — pseudo-legal moves that do NOT
    leave the moving side's king in check.

    Castling receives extra validation:
      1. King must not currently be in check.
      2. King must not pass through an attacked square.
      3. King must not land on an attacked square (handled by normal filter).
    """
    pseudo = piece.get_pseudo_legal_moves(board, game_state)
    legal = []

    for to_row, to_col in pseudo:

        # Special castling validation
        if isinstance(piece, King) and abs(to_col - piece.col) == 2:
            # Rule 1: Cannot castle while in check
            if is_in_check(board, piece.color, game_state):
                continue

            # Rule 2: King cannot pass through an attacked square
            mid_col = (piece.col + to_col) // 2
            pass_board = _copy_board(board)
            pass_king = pass_board[piece.row][piece.col]
            pass_board[piece.row][mid_col] = pass_king
            pass_board[piece.row][piece.col] = None
            if pass_king:
                pass_king.col = mid_col
            sim = _SimState(game_state.en_passant_target)
            if is_in_check(pass_board, piece.color, sim):
                continue

        # General check: does this move leave our king in check?
        new_board, new_ep = apply_move_to_board(board, piece, to_row, to_col, game_state)
        sim = _SimState(new_ep)
        if not is_in_check(new_board, piece.color, sim):
            legal.append((to_row, to_col))

    return legal


# ---------------------------------------------------------------------------
# Game-ending condition checks
# ---------------------------------------------------------------------------

def has_any_legal_moves(color, board, game_state) -> bool:
    """Return True if *color* has at least one legal move."""
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p is not None and p.color == color:
                if get_legal_moves(p, board, game_state):
                    return True
    return False


def is_checkmate(color, board, game_state) -> bool:
    """Return True if *color* is checkmated (in check with no legal moves)."""
    return (is_in_check(board, color, game_state)
            and not has_any_legal_moves(color, board, game_state))


def is_stalemate(color, board, game_state) -> bool:
    """Return True if *color* is stalemated (not in check but no legal moves)."""
    return (not is_in_check(board, color, game_state)
            and not has_any_legal_moves(color, board, game_state))


def is_insufficient_material(board) -> bool:
    """
    Return True when neither side can force checkmate (K vs K, K+B vs K,
    K+N vs K, K+B vs K+B same-colour bishops).
    """
    from pieces import Bishop, Knight

    pieces = []
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p is not None and not isinstance(p, King):
                pieces.append(p)

    if len(pieces) == 0:
        return True   # K vs K

    if len(pieces) == 1:
        return isinstance(pieces[0], (Bishop, Knight))   # K+B or K+N vs K

    if len(pieces) == 2:
        b0, b1 = pieces
        if isinstance(b0, Bishop) and isinstance(b1, Bishop):
            # Same-colour bishops → draw
            if (b0.row + b0.col) % 2 == (b1.row + b1.col) % 2:
                return True

    return False

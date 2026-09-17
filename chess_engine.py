import chess

class ChessGame:
    def __init__(self):
        self.board = chess.Board()

    def get_fen(self):
        return self.board.fen()

    def make_move(self, move_san):
        try:
            move = self.board.parse_san(move_san)
            if move in self.board.legal_moves:
                self.board.push(move)
                return True, self.get_game_status()
            return False, "نقلة غير قانونية!"
        except ValueError:
            return False, "صيغة نقلة غير صحيحة!"

    def get_legal_moves(self):
        return [self.board.san(m) for m in self.board.legal_moves]

    def get_game_status(self):
        if self.board.is_checkmate():
            return "checkmate"
        elif self.board.is_stalemate() or self.board.is_insufficient_material():
            return "draw"
        elif self.board.is_check():
            return "check"
        return "ongoing"

    def render_board_ascii(self):
        return str(self.board)


"""Translates raw UI input (pixel clicks/jumps, wait durations, promotion
choices) into GameEngine calls via BoardMapper. The only door from input
events into the engine - GameEngine itself never sees a pixel.
"""


class Controller:
    def __init__(self, engine, board_mapper):
        self._engine = engine
        self._board_mapper = board_mapper

    def click(self, x_px, y_px):
        position = self._board_mapper.cell_at(x_px, y_px)
        self._engine.click(position.row, position.col)

    def jump(self, x_px, y_px):
        position = self._board_mapper.cell_at(x_px, y_px)
        self._engine.jump(position.row, position.col)

    def wait(self, ms):
        self._engine.wait(ms)

    def choose_promotion(self, row, col, piece_type):
        self._engine.choose_promotion(row, col, piece_type)
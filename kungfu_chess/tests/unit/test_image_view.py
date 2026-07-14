from kungfu_chess.model.piece import Piece
from kungfu_chess.view.renderer import CellView
from kungfu_chess.view.image_view import (
    ImageView,
    LIGHT_SQUARE_COLOR,
    DARK_SQUARE_COLOR,
    WHITE_PIECE_COLOR,
    BLACK_PIECE_COLOR,
)


def decode_ppm(ppm_bytes):
    """Minimal PPM (ASCII P3) decoder used only to verify ImageView's
    output in tests - production code never needs to read this format
    back, only write it.
    """
    text = ppm_bytes.decode("ascii")
    lines = text.strip("\n").split("\n")
    assert lines[0] == "P3"
    width, height = (int(value) for value in lines[1].split())
    assert lines[2] == "255"

    pixels = []
    for row_line in lines[3:]:
        values = [int(v) for v in row_line.split()]
        row = [tuple(values[i : i + 3]) for i in range(0, len(values), 3)]
        pixels.append(row)

    assert len(pixels) == height
    for row in pixels:
        assert len(row) == width
    return width, height, pixels


def test_render_ppm_of_empty_layout_is_a_zero_sized_image():
    ppm_bytes = ImageView().render_ppm([])
    assert ppm_bytes == b"P3\n0 0\n255\n"


def test_render_ppm_paints_empty_light_square_with_light_color():
    cell = CellView(row=0, col=0, piece=None, x_px=0, y_px=0, size_px=2)
    width, height, pixels = decode_ppm(ImageView().render_ppm([cell]))
    assert (width, height) == (2, 2)
    for row in pixels:
        for pixel in row:
            assert pixel == LIGHT_SQUARE_COLOR


def test_render_ppm_paints_empty_dark_square_with_dark_color():
    cell = CellView(row=0, col=1, piece=None, x_px=0, y_px=0, size_px=2)
    _, _, pixels = decode_ppm(ImageView().render_ppm([cell]))
    for row in pixels:
        for pixel in row:
            assert pixel == DARK_SQUARE_COLOR


def test_render_ppm_paints_a_white_piece_block_inset_from_the_square_border():
    cell = CellView(row=0, col=0, piece=Piece(color="w", kind="K"), x_px=0, y_px=0, size_px=10)
    _, _, pixels = decode_ppm(ImageView().render_ppm([cell]))
    assert pixels[0][0] == LIGHT_SQUARE_COLOR  # corner: base square color
    assert pixels[5][5] == WHITE_PIECE_COLOR  # center: piece color


def test_render_ppm_paints_a_black_piece_block_inset_from_the_square_border():
    cell = CellView(row=0, col=0, piece=Piece(color="b", kind="R"), x_px=0, y_px=0, size_px=10)
    _, _, pixels = decode_ppm(ImageView().render_ppm([cell]))
    assert pixels[0][0] == LIGHT_SQUARE_COLOR
    assert pixels[5][5] == BLACK_PIECE_COLOR


def test_render_ppm_places_cells_at_their_pixel_offsets():
    cells = [
        CellView(row=0, col=0, piece=None, x_px=0, y_px=0, size_px=2),
        CellView(row=0, col=1, piece=None, x_px=2, y_px=0, size_px=2),
    ]
    width, height, pixels = decode_ppm(ImageView().render_ppm(cells))
    assert (width, height) == (4, 2)
    assert pixels[0][0] == LIGHT_SQUARE_COLOR
    assert pixels[0][2] == DARK_SQUARE_COLOR

"""Pure sprite-file path building - no I/O, no dependency on anything
else in view/. Split out from opencv_view.py so both it and
sprite_registry.py can share this without an import cycle between the
two (opencv_view composes a SpriteRegistry; SpriteRegistry needs this
same path-building logic to build a SpriteSet's frame_paths).
"""

import os


def sprite_path(assets_pieces_dir, piece_color, piece_kind, folder_name, frame_filename="1.png"):
    return os.path.join(assets_pieces_dir, f"{piece_color}{piece_kind}", "states", folder_name, "sprites", frame_filename)
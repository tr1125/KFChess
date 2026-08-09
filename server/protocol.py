"""The `{"type", "payload"}` wire envelope: one named constant per message
type (see KFChess_Server_Plan.md's wire protocol reference and Sec 7's DRY
rule - never re-type a message-type string as a bare literal elsewhere) plus
encode/decode helpers shared by both server and client.
"""

import json

MSG_LOGIN = "login"
MSG_LOGIN_OK = "login_ok"
MSG_LOGIN_ERROR = "login_error"
MSG_MOVE = "move"
MSG_JUMP = "jump"
MSG_PROMOTE = "promote"
MSG_MOVE_STARTED = "move_started"
MSG_STATE = "state"
MSG_GAME_STARTED = "game_started"
MSG_GAME_ENDED = "game_ended"
# Not yet in KFChess_Server_Plan.md's protocol table as of Stage 2 - added
# here for the "room full" / malformed-envelope case (Sec 2 invites new
# types to be added as needed, keeping the doc in sync with the code).
MSG_ERROR = "error"

# game_ended's "result"/"reason" payload values (Stage 3) - named once
# here rather than re-typed as bare literals in rooms.py/rating.py.
RESULT_WHITE_WINS = "white_wins"
RESULT_BLACK_WINS = "black_wins"
RESULT_DRAW = "draw"

REASON_CAPTURE = "capture"
REASON_INSUFFICIENT_MATERIAL = "insufficient_material"


class ProtocolError(Exception):
    """Raised when decode() is handed something that isn't a valid
    `{"type", "payload"}` envelope."""


def encode(msg_type, payload):
    return json.dumps({"type": msg_type, "payload": payload})


def decode(raw):
    try:
        envelope = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise ProtocolError(f"invalid JSON: {error}") from error

    if not isinstance(envelope, dict) or "type" not in envelope or "payload" not in envelope:
        raise ProtocolError(f"not a {{'type','payload'}} envelope: {envelope!r}")

    return envelope["type"], envelope["payload"]
import pytest

from server.protocol import encode, decode, ProtocolError, MSG_MOVE


def test_encode_produces_a_type_payload_envelope():
    raw = encode(MSG_MOVE, {"from": "e2", "to": "e4"})
    assert decode(raw) == (MSG_MOVE, {"from": "e2", "to": "e4"})


def test_decode_round_trips_an_empty_payload():
    raw = encode("play", {})
    assert decode(raw) == ("play", {})


def test_decode_raises_protocol_error_on_invalid_json():
    with pytest.raises(ProtocolError):
        decode("not json at all")


def test_decode_raises_protocol_error_when_type_is_missing():
    with pytest.raises(ProtocolError):
        decode('{"payload": {}}')


def test_decode_raises_protocol_error_when_payload_is_missing():
    with pytest.raises(ProtocolError):
        decode('{"type": "move"}')


def test_decode_raises_protocol_error_when_envelope_is_not_an_object():
    with pytest.raises(ProtocolError):
        decode("[1, 2, 3]")
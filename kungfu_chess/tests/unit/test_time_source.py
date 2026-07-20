from kungfu_chess.driver.time_source import WallClock


def test_now_ms_reflects_time_time_in_milliseconds(monkeypatch):
    monkeypatch.setattr("kungfu_chess.driver.time_source.time.time", lambda: 10.0)
    assert WallClock().now_ms() == 10000.0


def test_now_ms_changes_as_time_time_changes(monkeypatch):
    values = iter([1.0, 1.5])
    monkeypatch.setattr("kungfu_chess.driver.time_source.time.time", lambda: next(values))
    clock = WallClock()
    first = clock.now_ms()
    second = clock.now_ms()
    assert second - first == 500.0
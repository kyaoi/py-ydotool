from py_ydotool import MouseButton


def test_mouse_button_constants() -> None:
    assert MouseButton.LEFT == "0xC0"
    assert MouseButton.RIGHT == "0xC1"
    assert MouseButton.MIDDLE == "0xC2"
    assert MouseButton.SIDE == "0xC3"
    assert MouseButton.EXTRA == "0xC4"
    assert MouseButton.FORWARD == "0xC5"
    assert MouseButton.BACK == "0xC6"
    assert MouseButton.TASK == "0xC7"

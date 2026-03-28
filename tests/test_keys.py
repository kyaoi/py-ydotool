from py_ydotool import Key


def test_letter_and_number_keys() -> None:
    assert Key.A == 30
    assert Key.I == 23
    assert Key.O == 24
    assert Key.Z == 44
    assert Key.NUM_1 == 2
    assert Key.NUM_0 == 11


def test_modifier_keys_and_aliases() -> None:
    assert Key.LEFT_CTRL == 29
    assert Key.RIGHT_CTRL == 97
    assert Key.LEFT_SHIFT == 42
    assert Key.RIGHT_SHIFT == 54
    assert Key.LEFT_ALT == 56
    assert Key.RIGHT_ALT == 100
    assert Key.LEFT_META == 125
    assert Key.RIGHT_META == 126

    assert Key.CTRL == Key.LEFT_CTRL
    assert Key.SHIFT == Key.LEFT_SHIFT
    assert Key.ALT == Key.LEFT_ALT
    assert Key.META == Key.LEFT_META


def test_navigation_and_editing_keys() -> None:
    assert Key.ENTER == 28
    assert Key.ESC == 1
    assert Key.TAB == 15
    assert Key.SPACE == 57
    assert Key.BACKSPACE == 14
    assert Key.INSERT == 110
    assert Key.DELETE == 111
    assert Key.HOME == 102
    assert Key.END == 107
    assert Key.PAGEUP == 104
    assert Key.PAGEDOWN == 109
    assert Key.UP == 103
    assert Key.LEFT == 105
    assert Key.RIGHT == 106
    assert Key.DOWN == 108


def test_symbol_keys() -> None:
    assert Key.MINUS == 12
    assert Key.EQUAL == 13
    assert Key.LEFTBRACE == 26
    assert Key.RIGHTBRACE == 27
    assert Key.SEMICOLON == 39
    assert Key.APOSTROPHE == 40
    assert Key.GRAVE == 41
    assert Key.BACKSLASH == 43
    assert Key.COMMA == 51
    assert Key.DOT == 52
    assert Key.SLASH == 53


def test_function_and_lock_keys() -> None:
    assert Key.F1 == 59
    assert Key.F12 == 88
    assert Key.CAPSLOCK == 58
    assert Key.NUMLOCK == 69
    assert Key.SCROLLLOCK == 70


def test_keypad_keys() -> None:
    assert Key.KP_7 == 71
    assert Key.KP_8 == 72
    assert Key.KP_9 == 73
    assert Key.KP_MINUS == 74
    assert Key.KP_4 == 75
    assert Key.KP_5 == 76
    assert Key.KP_6 == 77
    assert Key.KP_PLUS == 78
    assert Key.KP_1 == 79
    assert Key.KP_2 == 80
    assert Key.KP_3 == 81
    assert Key.KP_0 == 82
    assert Key.KP_DOT == 83
    assert Key.KP_ENTER == 96
    assert Key.KP_SLASH == 98
    assert Key.KP_ASTERISK == 55


def test_system_keys() -> None:
    assert Key.SYSRQ == 99
    assert Key.PRINT_SCREEN == Key.SYSRQ
    assert Key.PAUSE == 119
    assert Key.COMPOSE == 127
    assert Key.MENU == 139

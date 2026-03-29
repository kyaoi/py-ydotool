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


def test_editing_and_launcher_keys() -> None:
    assert Key.COPY == 133
    assert Key.OPEN == 134
    assert Key.PASTE == 135
    assert Key.FIND == 136
    assert Key.CUT == 137
    assert Key.HELP == 138
    assert Key.MENU == 139
    assert Key.CALC == 140
    assert Key.SETUP == 141
    assert Key.SLEEP == 142
    assert Key.WAKEUP == 143
    assert Key.FILE == 144
    assert Key.SENDFILE == 145
    assert Key.DELETEFILE == 146
    assert Key.XFER == 147
    assert Key.PROG1 == 148
    assert Key.PROG2 == 149
    assert Key.WWW == 150
    assert Key.SCREENLOCK == 152
    assert Key.ROTATE_DISPLAY == 153
    assert Key.MAIL == 155
    assert Key.BOOKMARKS == 156
    assert Key.COMPUTER == 157
    assert Key.BACK == 158
    assert Key.FORWARD == 159
    assert Key.HOMEPAGE == 172
    assert Key.REFRESH == 173


def test_media_and_brightness_keys() -> None:
    assert Key.NEXTSONG == 163
    assert Key.PLAYPAUSE == 164
    assert Key.PREVIOUSSONG == 165
    assert Key.STOPCD == 166
    assert Key.BRIGHTNESSDOWN == 224
    assert Key.BRIGHTNESSUP == 225
    assert Key.MEDIA == 226
    assert Key.KBDILLUMTOGGLE == 228
    assert Key.KBDILLUMDOWN == 229
    assert Key.KBDILLUMUP == 230
    assert Key.MICMUTE == 248


def test_audio_and_power_keys() -> None:
    assert Key.MUTE == 113
    assert Key.VOLUMEDOWN == 114
    assert Key.VOLUMEUP == 115
    assert Key.POWER == 116


def test_japanese_input_keys() -> None:
    assert Key.KATAKANA == 90
    assert Key.HIRAGANA == 91
    assert Key.HENKAN == 92
    assert Key.KATAKANAHIRAGANA == 93
    assert Key.MUHENKAN == 94
    assert Key.HANGEUL == 122
    assert Key.HANJA == 123
    assert Key.YEN == 124


def test_media_transport_and_system_keys() -> None:
    assert Key.EJECTCD == 161
    assert Key.RECORD == 167
    assert Key.REWIND == 168
    assert Key.PHONE == 169
    assert Key.CONFIG == 171
    assert Key.PLAYCD == 200
    assert Key.PAUSECD == 201

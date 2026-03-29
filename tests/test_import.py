from py_ydotool import PyYDoTool, __version__


def test_package_import() -> None:
    assert PyYDoTool is not None


def test_version_string() -> None:
    assert __version__ == "0.1.0"

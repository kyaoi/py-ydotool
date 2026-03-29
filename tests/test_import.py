from importlib import resources

from py_ydotool import PyYDoTool, __version__


def test_package_import() -> None:
    assert PyYDoTool is not None


def test_version_string_matches_version_file() -> None:
    version_path = resources.files("py_ydotool").joinpath("VERSION")
    version_text = version_path.read_text(encoding="utf-8").strip()
    assert __version__ == version_text

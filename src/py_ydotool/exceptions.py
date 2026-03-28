class PyYDoToolError(RuntimeError):
    """Base exception for py_ydotool."""


class CommandNotFoundError(PyYDoToolError):
    """Raised when a required external command is missing."""


class CommandExecutionError(PyYDoToolError):
    """Raised when an external command exits with a non-zero status."""


class ClipboardUnavailableError(PyYDoToolError):
    """Raised when no supported clipboard backend is available."""

class PyYDoToolError(RuntimeError):
    """Base exception for py_ydotool."""


class CommandNotFoundError(PyYDoToolError):
    """Raised when a required external command is missing."""


class CommandExecutionError(PyYDoToolError):
    """Raised when an external command exits with a non-zero status."""


class ClipboardUnavailableError(PyYDoToolError):
    """Raised when no supported clipboard backend is available."""


class CommandTimeoutError(PyYDoToolError):
    """Raised when an external command exceeds the configured timeout."""


class DaemonError(PyYDoToolError):
    """Base exception for ydotoold lifecycle helper failures."""


class DaemonStartError(CommandExecutionError, DaemonError):
    """Raised when ydotoold exits before it becomes ready."""


class DaemonReadyTimeoutError(CommandTimeoutError, DaemonError):
    """Raised when ydotoold does not become ready in time."""


class TextInputUnavailableError(PyYDoToolError):
    """Raised when no supported text input backend is available."""

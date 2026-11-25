"""System power commands used by the optional auto-shutdown."""

import platform

_COMMANDS: dict[str, list[str]] = {
    "Linux": ["systemctl", "poweroff"],
    "Darwin": ["osascript", "-e", 'tell application "System Events" to shut down'],
    "Windows": ["shutdown", "/s", "/t", "0"],
}


def poweroff_command(system: str | None = None) -> list[str]:
    """Return the command that powers the machine off on ``system``."""
    name = system or platform.system()
    try:
        return list(_COMMANDS[name])
    except KeyError:
        raise ValueError(f"unsupported platform for auto-shutdown: {name}") from None

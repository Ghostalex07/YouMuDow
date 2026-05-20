import platform
import subprocess


def notify(title: str, message: str) -> None:
    try:
        system = platform.system()
        if system == "Linux":
            subprocess.Popen(
                ["notify-send", title, message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif system == "Darwin":
            script = f'display notification "{message}" with title "{title}"'
            subprocess.Popen(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif system == "Windows":
            try:
                from plyer import notification
                notification.notify(title=title, message=message, timeout=5)
            except ImportError:
                pass
    except Exception:
        pass

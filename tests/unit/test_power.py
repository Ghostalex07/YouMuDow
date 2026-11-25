import pytest

from youmudow.domain.power import poweroff_command


def test_poweroff_commands_per_platform():
    assert poweroff_command("Linux") == ["systemctl", "poweroff"]
    assert poweroff_command("Windows") == ["shutdown", "/s", "/t", "0"]
    assert poweroff_command("Darwin")[0] == "osascript"


def test_unknown_platform_is_rejected():
    with pytest.raises(ValueError):
        poweroff_command("BeOS")

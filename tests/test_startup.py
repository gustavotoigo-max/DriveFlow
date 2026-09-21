from unittest.mock import MagicMock, patch

from driveflow import startup


def test_startup_registers_only_current_users_named_entry(tmp_path):
    executable = tmp_path / 'Pasta com espacos' / 'DriveFlow.exe'
    registry = MagicMock()
    registry.HKEY_CURRENT_USER = 'current-user'
    with patch.object(startup, 'winreg', registry):
        startup.set_enabled(True, executable)
    registry.CreateKeyEx.assert_called_once_with('current-user', startup.RUN_KEY, 0, registry.KEY_SET_VALUE)
    args = registry.SetValueEx.call_args.args
    assert args[1] == 'DriveFlow'
    assert args[4] == '"' + str(executable.resolve()) + '"'


def test_disabling_startup_removes_only_driveflow_entry():
    registry = MagicMock()
    with patch.object(startup, 'winreg', registry):
        startup.set_enabled(False)
    assert registry.DeleteValue.call_args.args[1] == 'DriveFlow'
    registry.SetValueEx.assert_not_called()

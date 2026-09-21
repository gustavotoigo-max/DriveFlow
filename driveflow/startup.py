"""Start the app at sign-in for the current Windows user only."""
import subprocess
import sys
from pathlib import Path
import winreg

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
VALUE_NAME = 'DriveFlow'


def launch_command(executable=None):
    if executable:
        args = [str(Path(executable).resolve())]
    elif getattr(sys, 'frozen', False):
        args = [sys.executable]
    else:
        pythonw = Path(sys.executable).with_name('pythonw.exe')
        args = [str(pythonw if pythonw.exists() else Path(sys.executable)),
                str(Path(__file__).resolve().parents[1] / 'run.py')]
    return subprocess.list2cmdline(args)


def set_enabled(enabled, executable=None):
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, launch_command(executable))
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass

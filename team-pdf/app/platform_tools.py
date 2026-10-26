"""Per-user locations and opening files without system installation."""
import os
import pathlib
import subprocess
import sys
import webbrowser

def downloads_dir():
    if sys.platform == 'win32':
        try:
            import winreg
            key_path = r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                path = winreg.QueryValueEx(key, '{374DE290-123F-4565-9164-39C4925E467B}')[0]
            if path:
                return pathlib.Path(os.path.expandvars(path))
        except (ImportError, OSError):
            pass
    return pathlib.Path.home() / 'Downloads'

def open_folder(path):
    if sys.platform == 'win32':
        os.startfile(str(path))
    elif sys.platform == 'darwin':
        subprocess.run(['/usr/bin/open', str(path)], check=True)
    else:
        subprocess.run(['xdg-open', str(path)], check=True)

def open_browser(url):
    return webbrowser.open(url, new=2)

def process_options():
    if sys.platform == 'win32':
        return {'creationflags': subprocess.CREATE_NO_WINDOW}
    return {}

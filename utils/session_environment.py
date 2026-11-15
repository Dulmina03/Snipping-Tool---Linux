"""Validate a genuine GNOME Wayland user-session environment without Qt."""
import os
from pathlib import Path
import stat


def session_problem(environment=None, uid=None):
    """Fail closed for missing/stale GUI environment; never guess wayland-0."""
    env = os.environ if environment is None else environment
    uid = os.getuid() if uid is None else uid
    if uid == 0:
        return 'Run as the logged-in desktop user, not root.'
    if env.get('XDG_SESSION_TYPE') != 'wayland':
        return 'The user manager needs XDG_SESSION_TYPE=wayland from the genuine GNOME session.'
    if 'gnome' not in env.get('XDG_CURRENT_DESKTOP', '').lower().split(':'):
        return 'This prototype requires a GNOME graphical session.'
    runtime = env.get('XDG_RUNTIME_DIR', '')
    if not runtime or not Path(runtime).is_absolute():
        return 'XDG_RUNTIME_DIR is missing or invalid.'
    display = env.get('WAYLAND_DISPLAY', '')
    if not display:
        return 'WAYLAND_DISPLAY is missing; import it only from a genuine GNOME terminal.'
    runtime = Path(runtime)
    wayland = Path(display) if Path(display).is_absolute() else runtime / display
    bus = runtime / 'bus'
    if env.get('DBUS_SESSION_BUS_ADDRESS') != f'unix:path={bus}':
        return 'The session D-Bus address must reference this user runtime bus.'
    try:
        if runtime.stat().st_uid != uid or not runtime.is_dir():
            return 'The runtime directory is not owned by the desktop user.'
        for label, path in (('Wayland', wayland), ('session D-Bus', bus)):
            metadata = path.stat()
            if not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != uid:
                return f'The {label} socket is unavailable or belongs to another user.'
    except OSError:
        return 'The Wayland/session D-Bus socket is unavailable; start only inside the active graphical session.'
    return None


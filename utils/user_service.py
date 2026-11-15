"""Generate manual or GNOME-login user-service profiles for this checkout.

Does not enable/start units, import editor environment, edit desktop entries or
create autostart entries. Session validation uses only the standard library.
"""
import argparse
import os
from pathlib import Path
import sys
import tempfile

from utils.desktop_entry import APP_ID, ROOT
from utils.session_environment import session_problem

UNIT_NAME = f'{APP_ID}.service'


def unit_quote(value, *, command=False):
    """Quote a systemd command argument, not a WorkingDirectory value."""
    value = str(value)
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError('Service paths cannot contain control characters')
    value = value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
    if command:
        value = value.replace('$', '$$')
    return '"' + value + '"'


def service_unit(project_root=ROOT, *, login_startup=False):
    root = Path(project_root).absolute()
    # Do not resolve this symlink: the venv path selects its Python environment.
    python = root / '.venv/bin/python'
    if not (root / 'main.py').is_file() or not python.is_file() or not os.access(python, os.X_OK):
        raise RuntimeError('The checkout must contain main.py and an executable .venv/bin/python')
    template = (ROOT / 'systemd' / f'{UNIT_NAME}.in').read_text(encoding='utf-8')
    unit_quote(root)  # Validate control characters before writing any directive.
    # WorkingDirectory consumes the whole value literally, unlike ExecStart.
    # '/.' keeps a trailing space/backslash in a directory name away from EOL.
    directory = str(root).replace('%', '%%') + '/.'
    content = template.replace('@ROOT@', directory).replace(
        '@PYTHON@', unit_quote(python)).replace('@MAIN@', unit_quote(root / 'main.py', command=True))
    if login_startup:
        # GNOME's installed target is Before=graphical-session.target. Wait for
        # that ready session, not for the target that now pulls this service in.
        content = content.replace('Stage 1 prototype;', 'Stage 2 login prototype;').replace(
            '# Manual-only: deliberately no [Install] / WantedBy / autostart entry.',
            '# Enable explicitly only after validating the manual service lifecycle.').replace(
            'Requisite=graphical-session.target', 'Requisite=gnome-session.target').replace(
            'After=graphical-session.target', 'After=gnome-session.target')
        content += '\n[Install]\nWantedBy=graphical-session.target\n'
    return content


def install_service(project_root=ROOT, unit_directory=None, *, login_startup=False, replace_known=False):
    directory = Path(unit_directory) if unit_directory is not None else (
        Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'systemd/user')
    content = service_unit(project_root, login_startup=login_startup)
    target = directory / UNIT_NAME
    previous = None
    if target.is_symlink():
        raise RuntimeError(f'Existing service symlink preserved: {target}')
    if target.exists():
        previous = target.read_text(encoding='utf-8')
        if previous == content:
            return target
        other_profile = service_unit(project_root, login_startup=not login_startup)
        if not replace_known or previous != other_profile:
            raise RuntimeError(f'Existing service preserved; review manually: {target}')
    directory.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory,
                                         prefix=f'.{UNIT_NAME}-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        temporary.chmod(0o644)
        if previous is not None:
            # An explicit, exact-profile migration only. Never treat a managed
            # marker as permission to overwrite arbitrary user edits.
            if target.is_symlink() or target.read_text(encoding='utf-8') != previous:
                raise RuntimeError(f'Service changed while preparing installation; preserved: {target}')
            temporary.replace(target)
            return target
        # Publish without overwriting another installer or a custom unit.
        try:
            os.link(temporary, target)
        except FileExistsError:
            if target.is_symlink() or target.read_text(encoding='utf-8') != content:
                raise RuntimeError(f'Existing service preserved; review manually: {target}')
        return target
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)



def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--print', action='store_true', help='Print a generated unit without installing')
    action.add_argument('--install', action='store_true', help='Install only; never enable/start or import environment')
    action.add_argument('--check-session', action='store_true', help='ExecCondition check, no Qt startup')
    parser.add_argument('--login-startup', action='store_true', help='Generate the GNOME login profile; does not enable it')
    parser.add_argument('--replace-known', action='store_true', help='Explicitly replace only the exact other generated profile')
    args = parser.parse_args(argv)
    if args.check_session and (args.login_startup or args.replace_known):
        parser.error('Profile options cannot be used with --check-session')
    if args.replace_known and not args.install:
        parser.error('--replace-known requires --install')
    try:
        if args.check_session:
            problem = session_problem()
            if problem:
                print('AI Snipping Tool service skipped: ' + problem, file=sys.stderr)
                return 1  # ExecCondition 1 skips cleanly, without a restart loop.
            return 0
        if args.print:
            print(service_unit(login_startup=args.login_startup), end='')
        else:
            print(install_service(login_startup=args.login_startup, replace_known=args.replace_known))
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

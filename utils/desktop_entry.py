"""Generate a checkout-specific launcher from a portable desktop template."""
import os
from pathlib import Path
import sys

APP_ID = 'com.dulmina.aisnippingtool'
ROOT = Path(__file__).resolve().parents[1]


def exec_quote(value):
    # Desktop Exec escaping is not shell quoting. Double % escapes field codes.
    value = str(value)
    if '\n' in value or '\r' in value:
        raise ValueError('Launcher paths cannot contain newlines')
    value = value.replace('\\', '\\\\\\\\')
    for char in ('"', '`', '$'):
        value = value.replace(char, '\\\\' + char)
    return '"' + value.replace('%', '%%') + '"'


def desktop_entry(project_root=ROOT, python_bin=None):
    root = Path(project_root).absolute()
    python_bin = python_bin or sys.executable
    template = (ROOT / f'{APP_ID}.desktop').read_text(encoding='utf-8')
    return template.replace('@PYTHON@', exec_quote(python_bin)).replace(
        '@MAIN@', exec_quote(root / 'main.py'))


def ensure_desktop_entry(project_root=ROOT, python_bin=None, applications_dir=None):
    apps = Path(applications_dir) if applications_dir is not None else (
        Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'applications')
    target = apps / f'{APP_ID}.desktop'
    content = desktop_entry(project_root, python_bin)
    if target.exists():
        previous = target.read_text(encoding='utf-8')
        if previous == content:
            return target
        # Migrate our generated legacy entry only. Leave custom launchers intact.
        legacy = (f'StartupWMClass={APP_ID}' in previous
                  and 'Name=AI Snipping Tool\n' in previous
                  and '/ui/capture_menu.py' in previous)
        managed = 'X-AISnippingTool-Managed=true' in previous
        if not (legacy or managed):
            raise RuntimeError(f'Custom desktop entry preserved; review manually: {target}')
    apps.mkdir(parents=True, exist_ok=True)
    # Atomic replace avoids a partially written launcher on interrupted startup.
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=apps,
                                     prefix=f'.{APP_ID}-', delete=False) as stream:
        stream.write(content)
        temporary = Path(stream.name)
    temporary.chmod(0o644)
    temporary.replace(target)
    return target

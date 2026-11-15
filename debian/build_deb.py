#!/usr/bin/python3
"""Rootless, offline binary .deb build. Only --fetch-wheel accesses the network."""
import argparse
import email.utils
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / 'debian'
WHEEL = json.loads((META / 'pytesseract-wheel.json').read_text())
# Only runtime modules; no tests, developer installers, PipeWire binaries or data.
SOURCES = ['main.py'] + [str(path.relative_to(ROOT)) for directory in ('ui', 'shortcuts', 'ocr', 'utils', 'capture')
    for path in sorted((ROOT / directory).glob('*.py'))
    if path.name not in ('user_service.py', 'screen_capture.py')]


def checked_wheel(path):
    path = Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != WHEEL['sha256']:
        raise ValueError('pytesseract wheel SHA-256 mismatch; refusing build')
    return path


def fetch_wheel(directory):
    """Explicit build-input acquisition, never an install/runtime operation."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / WHEEL['filename']
    if target.exists():
        return checked_wheel(target)
    data = urllib.request.urlopen(WHEEL['url'], timeout=30).read()
    if hashlib.sha256(data).hexdigest() != WHEEL['sha256']:
        raise ValueError('Downloaded wheel SHA-256 mismatch')
    # Do not overwrite a concurrently provided artifact.
    with target.open('xb') as stream:
        stream.write(data)
    return target


def copy(source, destination, mode=0o644):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    destination.chmod(mode)


def stage(destination, wheel):
    destination = Path(destination)
    checked_wheel(wheel)
    app = destination / 'usr/lib/ai-snipping-tool'
    doc = destination / 'usr/share/doc/ai-snipping-tool'
    for name in SOURCES:
        copy(ROOT / name, app / name)
    (app / '.packaged-install').write_text('Ubuntu 26.04 local prototype\n')
    assets = {
        'ai-snipping-tool': ('usr/bin/ai-snipping-tool', 0o755),
        'com.dulmina.aisnippingtool.desktop': ('usr/share/applications/com.dulmina.aisnippingtool.desktop', 0o644),
        'com.dulmina.aisnippingtool.service': ('usr/lib/systemd/user/com.dulmina.aisnippingtool.service', 0o644),
        'com.dulmina.aisnippingtool.svg': ('usr/share/icons/hicolor/scalable/apps/com.dulmina.aisnippingtool.svg', 0o644),
    }
    for source, (target, mode) in assets.items():
        copy(META / 'assets' / source, destination / target, mode)
    copy(META / 'copyright', doc / 'copyright')
    copy(META / 'README.install', doc / 'README.install')
    (doc / 'changelog.Debian.gz').write_bytes(gzip.compress((META / 'changelog').read_bytes(), mtime=0))
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            parts = PurePosixPath(name).parts
            # Strict file allowlist; never extract arbitrary wheel paths.
            if len(parts) == 2 and parts[0] == 'pytesseract' and parts[1].endswith('.py'):
                target = app / name
            elif name == 'pytesseract-0.3.13.dist-info/LICENSE':
                target = doc / 'pytesseract-LICENSE'
            else:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
    if not (app / 'pytesseract/pytesseract.py').is_file() or not (doc / 'pytesseract-LICENSE').is_file():
        raise ValueError('Expected licensed pytesseract payload missing')
    files = sorted(path for path in destination.rglob('*') if path.is_file())
    control = destination / 'DEBIAN'
    control.mkdir()
    installed_size = (sum(path.stat().st_size for path in files) + 1023) // 1024
    (control / 'control').write_text((META / 'control').read_text() + f'Installed-Size: {installed_size}\n')
    (control / 'md5sums').write_text(''.join(
        f'{hashlib.md5(path.read_bytes()).hexdigest()}  {path.relative_to(destination)}\n' for path in files))
    # No postinst/prerm, global enablement, user-file migration or downloads.
    destination.chmod(0o755)
    for path in destination.rglob('*'):
        if path.is_file():
            path.chmod(0o755 if path == destination / 'usr/bin/ai-snipping-tool' else 0o644)
        else:
            path.chmod(0o755)


def build(wheel, output):
    if subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip() != 'amd64':
        raise RuntimeError('This prototype targets amd64; cross-build is not validated')
    fields = dict(line.split(': ', 1) for line in (META / 'control').read_text().splitlines()
                  if line and not line[0].isspace())
    output = Path(output).absolute()
    output.mkdir(parents=True, exist_ok=True)
    target = output / f"{fields['Package']}_{fields['Version']}_{fields['Architecture']}.deb"
    if target.exists():
        raise FileExistsError(f'Existing artifact preserved: {target}; choose another --output directory')
    epoch = int(os.environ.get('SOURCE_DATE_EPOCH') or email.utils.parsedate_to_datetime(
        (META / 'changelog').read_text().split('  ')[-1].strip()).timestamp())
    environment = dict(os.environ, SOURCE_DATE_EPOCH=str(epoch), TZ='UTC', LC_ALL='C.UTF-8')
    with tempfile.TemporaryDirectory(prefix='snipping-deb-') as scratch:
        tree = Path(scratch) / 'root'
        stage(tree, wheel)
        for path in [tree, *tree.rglob('*')]:
            os.utime(path, (epoch, epoch))
        package = Path(scratch) / 'candidate.deb'
        subprocess.run(['dpkg-deb', '--root-owner-group', '-Zxz', '--build', str(tree), str(package)],
                       check=True, env=environment)
        # Atomic no-replace publication, even across filesystems.
        with tempfile.NamedTemporaryFile(dir=output, prefix='.candidate-', delete=False) as stream:
            temporary = Path(stream.name)
            with package.open('rb') as source:
                shutil.copyfileobj(source, stream)
        try:
            temporary.chmod(0o644)
            os.link(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)  # Only this builder's private staging file.
    print(target)
    print('SHA256 ' + hashlib.sha256(target.read_bytes()).hexdigest())
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch-wheel', type=Path, metavar='DIRECTORY', help='Explicit network acquisition of build input only')
    parser.add_argument('--wheel', type=Path, help='Already downloaded, hash-checked build input; build stays offline')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    if args.fetch_wheel:
        if args.wheel:
            parser.error('Choose --fetch-wheel or --wheel')
        print(fetch_wheel(args.fetch_wheel))
    elif args.wheel:
        build(args.wheel, args.output)
    else:
        parser.error('Supply --wheel for offline build, or --fetch-wheel for explicit input acquisition')


if __name__ == '__main__':
    main()

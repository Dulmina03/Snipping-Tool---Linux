#!/usr/bin/python3
"""Read/extract a candidate in private scratch space; never install/start anything."""
import argparse
import ast
import hashlib
import io
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET


def verify(package):
    package = Path(package).absolute()
    info = subprocess.check_output(['dpkg-deb', '-f', str(package)], text=True)
    assert 'Package: ai-snipping-tool\n' in info
    assert 'Architecture: amd64\n' in info
    data = subprocess.check_output(['dpkg-deb', '--fsys-tarfile', str(package)])
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            assert not path.is_absolute() and '..' not in path.parts, member.name
            assert member.isdir() or member.isfile(), member.name
            assert member.uid == 0 and member.gid == 0, member.name
            assert member.mode & 0o022 == 0, member.name
    with tempfile.TemporaryDirectory(prefix='snipping-deb-verify-') as scratch:
        root = Path(scratch)
        subprocess.run(['dpkg-deb', '-x', str(package), str(root)], check=True)
        subprocess.run(['dpkg-deb', '-e', str(package), str(root / 'DEBIAN')], check=True)
        assert sorted(p.name for p in (root / 'DEBIAN').iterdir()) == ['control', 'md5sums']
        for row in (root / 'DEBIAN/md5sums').read_text().splitlines():
            digest, name = row.split('  ', 1)
            assert hashlib.md5((root / name).read_bytes()).hexdigest() == digest, name
        for path in root.rglob('*'):
            if not path.is_file():
                continue
            name = str(path.relative_to(root))
            assert not any(token in name for token in ('.git/', '.venv/', '__pycache__/', 'tests/', 'tessdata/', 'capture/native/')), name
            content = path.read_bytes()
            assert b'/home/dulmina' not in content, name
            if b'/home/' in content:
                # Existing URI-decoding docstrings use /home/user examples.
                # They are not runtime paths; no other string may embed a home.
                assert path.suffix == '.py', name
                tree = ast.parse(content)
                docstrings = set()
                for node in ast.walk(tree):
                    body = getattr(node, 'body', None)
                    if isinstance(body, list) and body and isinstance(body[0], ast.Expr):
                        value = body[0].value
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            docstrings.add(id(value))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                        assert '/home/' not in node.value, (name, node.lineno)
            if path.suffix == '.py' or name == 'usr/bin/ai-snipping-tool':
                compile(content, name, 'exec')  # No .pyc writes.
        app = root / 'usr/lib/ai-snipping-tool'
        assert (app / '.packaged-install').is_file()
        assert not (app / 'utils/user_service.py').exists()
        assert (app / 'utils/session_environment.py').is_file()
        assert (app / 'pytesseract/pytesseract.py').is_file()
        assert (root / 'usr/bin/ai-snipping-tool').stat().st_mode & 0o777 == 0o755
        subprocess.run(['desktop-file-validate', str(root / 'usr/share/applications/com.dulmina.aisnippingtool.desktop')], check=True)
        ET.parse(root / 'usr/share/icons/hicolor/scalable/apps/com.dulmina.aisnippingtool.svg')
        version = subprocess.check_output([str(root / 'usr/bin/ai-snipping-tool'), '--version'], text=True).strip()
    print('PASS: control, root ownership, permissions, checksums, payload exclusions, no home paths, Python syntax, desktop, SVG, extracted launcher')
    print(version)
    print('SHA256 ' + hashlib.sha256(package.read_bytes()).hexdigest())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    verify(parser.parse_args().package)

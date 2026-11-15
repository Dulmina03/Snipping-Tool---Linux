"""Isolated package layout/resource tests; never install or touch a host service."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from utils import desktop_entry, user_service, session_environment
from ocr import ocr_engine

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('snipping_deb_builder', ROOT / 'debian/build_deb.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='snipping-package-test-')
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)

    def fixture_wheel(self):
        wheel = self.root / 'controlled.whl'
        with zipfile.ZipFile(wheel, 'w') as archive:
            archive.writestr('pytesseract/__init__.py', '# controlled fixture\n')
            archive.writestr('pytesseract/pytesseract.py', '# controlled fixture\n')
            archive.writestr('pytesseract-0.3.13.dist-info/LICENSE', 'controlled license fixture\n')
            archive.writestr('../../unexpected-file', 'must not extract')
            archive.writestr('tests/private.py', 'must not include')
        return wheel

    def test_packaged_desktop_preserves_user_launcher_and_needs_no_venv(self):
        app = self.root / 'usr/lib/ai-snipping-tool'
        app.mkdir(parents=True)
        (app / '.packaged-install').touch()
        installed = self.root / 'usr/share/applications' / f'{desktop_entry.APP_ID}.desktop'
        installed.parent.mkdir(parents=True)
        installed.write_text('[Desktop Entry]\nExec=/usr/bin/ai-snipping-tool\n')
        local = self.root / 'user-apps'
        local.mkdir()
        old = local / installed.name
        old.write_text('private user override; preserve\n')
        with patch.object(desktop_entry, 'ROOT', app):
            self.assertEqual(desktop_entry.ensure_desktop_entry(applications_dir=local), installed)
        self.assertEqual(old.read_text(), 'private user override; preserve\n')

    def test_missing_installed_desktop_fails_without_creating_launcher(self):
        app = self.root / 'usr/lib/ai-snipping-tool'
        app.mkdir(parents=True)
        (app / '.packaged-install').touch()
        local = self.root / 'user-apps'
        with patch.object(desktop_entry, 'ROOT', app):
            with self.assertRaisesRegex(RuntimeError, 'Installed desktop entry missing'):
                desktop_entry.ensure_desktop_entry(applications_dir=local)
        self.assertFalse(local.exists())

    def test_installed_ocr_uses_read_only_dependency_models_without_network(self):
        models = self.root / 'system-tessdata'
        models.mkdir()
        for lang in ('eng', 'sin'):
            (models / f'{lang}.traineddata').write_bytes(b'controlled model-location fixture')
        models.chmod(0o555)
        with patch.object(ocr_engine, 'is_packaged_install', return_value=True), \
             patch.object(ocr_engine, 'SYSTEM_TESSDATA_CANDIDATES', [models]), \
             patch.object(ocr_engine.urllib.request, 'urlopen', side_effect=AssertionError('network forbidden')):
            self.assertEqual(ocr_engine._setup_tessdata_dir(), models)
            self.assertIn(str(models), ocr_engine._build_config())
        self.assertEqual(sorted(p.name for p in models.iterdir()), ['eng.traineddata','sin.traineddata'])

    def test_installed_missing_models_fail_without_download_or_source_write(self):
        with patch.object(ocr_engine, 'is_packaged_install', return_value=True), \
             patch.object(ocr_engine, 'SYSTEM_TESSDATA_CANDIDATES', [self.root / 'missing']), \
             patch.object(ocr_engine.urllib.request, 'urlopen', side_effect=AssertionError('network forbidden')):
            with self.assertRaisesRegex(RuntimeError, 'language data missing'):
                ocr_engine._setup_tessdata_dir()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_installed_ocr_language_branch_uses_active_system_models(self):
        from PIL import Image
        models = self.root / 'system-models'
        models.mkdir()
        for lang in ('eng', 'sin'):
            (models / f'{lang}.traineddata').touch()
        with patch.object(ocr_engine, 'is_packaged_install', return_value=True), \
             patch.object(ocr_engine, 'SYSTEM_TESSDATA_CANDIDATES', [models]), \
             patch.object(ocr_engine.pytesseract, 'image_to_string', return_value='fixture') as recognize:
            ocr_engine.extract_text(Image.new('RGB', (10, 10), 'white'))
        self.assertIn('sin', [call.kwargs['lang'] for call in recognize.call_args_list])
        self.assertIn('sin+eng', [call.kwargs['lang'] for call in recognize.call_args_list])
        self.assertTrue(all(str(models) in call.kwargs['config'] for call in recognize.call_args_list))

    def test_session_guard_is_shared_with_accepted_development_service(self):
        self.assertIs(user_service.session_problem, session_environment.session_problem)

    def test_hash_failure_rejects_before_staging_payload(self):
        wheel = self.fixture_wheel()
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            builder.stage(self.root / 'stage', wheel)
        self.assertFalse((self.root / 'stage').exists())

    def test_offline_stage_whitelist_licenses_modes_no_scripts_or_unsafe_paths(self):
        wheel = self.fixture_wheel()
        with patch.dict(builder.WHEEL, sha256=hashlib.sha256(wheel.read_bytes()).hexdigest()), \
             patch.object(builder.urllib.request, 'urlopen', side_effect=AssertionError('network forbidden')):
            stage = self.root / 'stage'
            builder.stage(stage, wheel)
        self.assertEqual(stage.stat().st_mode & 0o777, 0o755)
        files = [str(p.relative_to(stage)) for p in stage.rglob('*') if p.is_file()]
        for forbidden in ('tests/', '.git/', '.venv/', '__pycache__/', 'tessdata/', 'capture/native/', 'user_service.py', 'screen_capture.py'):
            self.assertFalse(any(forbidden in name for name in files), forbidden)
        self.assertEqual(sorted(p.name for p in (stage / 'DEBIAN').iterdir()), ['control','md5sums'])
        self.assertEqual((stage / 'usr/bin/ai-snipping-tool').stat().st_mode & 0o777, 0o755)
        self.assertTrue((stage / 'usr/share/doc/ai-snipping-tool/pytesseract-LICENSE').is_file())
        self.assertFalse((self.root / 'unexpected-file').exists())
        for file in stage.rglob('*'):
            if file.is_file():
                self.assertNotIn(b'/home/dulmina', file.read_bytes())
        result = subprocess.run([str(stage / 'usr/bin/ai-snipping-tool'),'--version'],text=True,capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('0.3.1~stage3.1-1', result.stdout)

    def test_packaged_service_preserves_accepted_lifecycle_and_explicit_activation(self):
        unit = (ROOT / 'debian/assets/com.dulmina.aisnippingtool.service').read_text()
        for setting in ('Requisite=gnome-session.target', 'After=gnome-session.target',
                        'PartOf=graphical-session.target', 'Restart=on-failure',
                        'StartLimitIntervalSec=60', 'StartLimitBurst=3',
                        'WantedBy=graphical-session.target', 'KillMode=mixed',
                        'TimeoutStopSec=30', 'ExecStart=/usr/bin/ai-snipping-tool'):
            self.assertIn(setting, unit)
        self.assertNotIn('/home/', unit)
        self.assertNotIn('.venv', unit)
        self.assertNotIn('User=root', unit)

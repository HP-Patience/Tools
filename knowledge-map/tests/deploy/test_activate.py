import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('activate', Path(__file__).resolve().parents[2] / 'deploy/activate.py')
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class DeployTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='zhixu-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root / 'incoming').mkdir()

    def fixture(self, token='1-1', suffix='a'):
        folder = self.root / 'incoming' / token
        folder.mkdir()
        (folder / 'assets').mkdir()
        version = '20260910000000-' + suffix * 10
        info = dict(version=version, builtAt='2026-09-10T00:00:00Z', sourceHash='a'*64, mapHash='b'*64)
        files = {'index.html': f'<script src="/versions/{version}/assets/app.js"></script>',
                 'assets/app.js': 'test', 'build-info.json': json.dumps(info)}
        for name, content in files.items():
            (folder / name).write_bytes(content.encode())
        manifest = dict(schemaVersion=1, **info, files={n: hashlib.sha256(c.encode()).hexdigest() for n, c in files.items()})
        (folder / 'manifest.json').write_text(json.dumps(manifest))
        return folder, version

    def test_verify(self):
        folder, version = self.fixture()
        self.assertEqual(deploy.verify(folder)['version'], version)

    def test_tampering_preserves_current(self):
        _, first = self.fixture()
        deploy.activate(self.root, '1-1')
        second, _ = self.fixture('2-1', 'b')
        (second / 'assets/app.js').write_text('corrupted')
        with self.assertRaises(ValueError):
            deploy.activate(self.root, '2-1')
        self.assertEqual((self.root / 'current').resolve().name, first)

    def test_atomic_switch_previous_and_rollback(self):
        _, first = self.fixture()
        deploy.activate(self.root, '1-1')
        _, second = self.fixture('2-1', 'b')
        deploy.activate(self.root, '2-1')
        self.assertEqual((self.root / 'current').resolve().name, second)
        self.assertEqual((self.root / 'previous').resolve().name, first)
        deploy.rollback(self.root, first)
        self.assertEqual((self.root / 'current').resolve().name, first)
        self.assertEqual(json.loads((self.root / 'last-run.json').read_text())['order'], [2, 1])

    def test_older_run_rejected(self):
        self.fixture('2-1')
        deploy.activate(self.root, '2-1')
        self.fixture('1-1', 'b')
        with self.assertRaises(ValueError):
            deploy.activate(self.root, '1-1')

    def test_additional_file_rejected(self):
        folder, _ = self.fixture()
        (folder / '.env').write_text('secret')
        with self.assertRaises(ValueError):
            deploy.verify(folder)

    def test_path_traversal(self):
        for value in ['../../etc', '-1-1', '1-1;whoami', '0-1']:
            with self.assertRaises(ValueError):
                deploy.activate(self.root, value)
        with self.assertRaises(ValueError):
            deploy.rollback(self.root, '../current')

    def test_symlink_rejected(self):
        folder, _ = self.fixture()
        (folder / 'assets/link.js').symlink_to(folder / 'assets/app.js')
        with self.assertRaises(ValueError):
            deploy.verify(folder)

    def test_same_version_rerun_allowed(self):
        _, version = self.fixture()
        deploy.activate(self.root, '1-1')
        self.fixture('1-2')
        self.assertEqual(deploy.activate(self.root, '1-2'), version)

    def test_version_collision(self):
        self.fixture()
        deploy.activate(self.root, '1-1')
        folder, _ = self.fixture('2-1')
        manifest = json.loads((folder / 'manifest.json').read_text())
        raw = b'changed'
        (folder / 'assets/app.js').write_bytes(raw)
        manifest['files']['assets/app.js'] = hashlib.sha256(raw).hexdigest()
        (folder / 'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            deploy.activate(self.root, '2-1')


if __name__ == '__main__':
    unittest.main()

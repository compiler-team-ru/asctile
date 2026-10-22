"""Regression tests for artifact selection and package content boundaries."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import resolve
import publish
from target import get_target, artifact_suffix, wheel_tag

spec = importlib.util.spec_from_file_location('wheel_check', Path(__file__).with_name('check-wheel.py'))
wheel_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wheel_check)
SHA = 'a' * 40


class RecipeTests(unittest.TestCase):
    def verify_publication(self, responses):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'artifact').mkdir()
            (root / 'artifact/build-passport.json').write_text(json.dumps({'version': '1.1.1.dev1', 'wheel': 'checked.whl'}))
            original = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {'PUBLISH_SHA256': 'b' * 64}), \
                     patch.object(publish.urllib.request, 'urlopen', side_effect=[io.BytesIO(json.dumps(r).encode()) for r in responses]), \
                     patch.object(publish.time, 'sleep') as sleep:
                    publish.verify_published()
                    return sleep.call_count
            finally:
                os.chdir(original)

    def test_wait_for_new_file_in_existing_release(self):
        stale = {'urls': [{'filename': 'other-target.whl', 'digests': {'sha256': 'a' * 64}}]}
        ready = {'urls': [{'filename': 'checked.whl', 'digests': {'sha256': 'b' * 64}}]}
        self.assertEqual(self.verify_publication([stale, ready]), 1)

    def test_reject_wrong_published_bytes(self):
        with self.assertRaises(AssertionError):
            self.verify_publication([{'urls': [{'filename': 'checked.whl', 'digests': {'sha256': 'a' * 64}}]}])

    def test_missing_published_file_never_passes(self):
        with self.assertRaises(RuntimeError):
            self.verify_publication([{'urls': []}] * 6)

    def resolve_case(self, expired=False, conclusion='success', force=False, target_name='cp310-aarch64'):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'ci').mkdir()
            (root / '.github/workflows').mkdir(parents=True)
            (root / '.github/workflows/wheels.yml').write_text('recipe')
            (root / 'README.md').write_text('description')
            (root / '.dockerignore').write_text('*')
            artifact = f'wheel-{SHA}-{resolve.recipe_digest(root)[:16]}-{artifact_suffix(get_target(target_name))}'
            responses = [
                {'default_branch': 'v2'},
                {'sha': SHA, 'commit': {'committer': {'date': '2026-10-21T00:00:00Z'}}},
                {'artifacts': [{'name': artifact, 'expired': expired, 'workflow_run': {'id': 1}}]},
                {'conclusion': conclusion},
            ]
            with patch.object(resolve, '__file__', str(root / 'ci/resolve.py')), patch.object(resolve, 'api', side_effect=responses), patch.dict(os.environ, {
                'INPUT_SOURCE_SHA': '', 'INPUT_FORCE': str(force).lower(), 'BUILD_TARGET': target_name,
                'GITHUB_REPOSITORY': 'owner/wheels', 'GITHUB_OUTPUT': str(root / 'output'),
            }):
                resolve.main()
            return json.loads((root / 'source.json').read_text())['build']

    def test_skip_successful_artifact(self):
        for target in ('cp310-aarch64', 'cp311-x86_64', 'cp310-x86_64'):
            self.assertFalse(self.resolve_case(target_name=target))

    def test_retry_failed_build(self):
        self.assertTrue(self.resolve_case(conclusion='failure'))

    def test_rebuild_expired_artifact(self):
        self.assertTrue(self.resolve_case(expired=True))

    def test_force_rebuild(self):
        self.assertTrue(self.resolve_case(force=True))

    def test_invalid_source_ref(self):
        for value in ('main', 'a' * 39, SHA + '\nbuild=false'):
            with self.assertRaises(ValueError):
                resolve.valid_sha(value)

    def test_payload_boundaries(self):
        dist = 'pyasc_dev-1.1.1.dev1.dist-info'
        for name in ('asc/runtime/__pycache__/jit.pyc', 'asc/token.txt', 'asc/../../secret.py', 'tests/test.py', 'build/native.so', dist + '/credentials.json'):
            self.assertFalse(wheel_check.allowed(name, dist), name)
        for name in ('asc/runtime/jit.py', get_target()['native'], dist + '/licenses/LICENSE'):
            self.assertTrue(wheel_check.allowed(name, dist), name)

    def test_bundled_library_boundary(self):
        dist = 'pyasc_dev-1.1.1.dev1.dist-info'
        arm, x86 = get_target('cp310-aarch64'), get_target('cp311-x86_64')
        for name in ('pyasc_dev.libs/libzstd-a1561916.so.1.4.8', dist + '/licenses/LICENSE-ZSTD.txt', dist + '/sboms/auditwheel.cdx.json'):
            self.assertTrue(wheel_check.allowed(name, dist, arm))
            self.assertFalse(wheel_check.allowed(name, dist, x86))
        self.assertFalse(wheel_check.allowed('pyasc_dev.libs/libzstd-a1561916.so.1.5.5', dist, arm))

    def test_native_target_boundary(self):
        targets = [get_target(name) for name in ('cp310-aarch64', 'cp311-x86_64', 'cp310-x86_64')]
        dist = 'pyasc_dev-1.1.1.dev1.dist-info'
        for target in targets:
            for other in targets:
                self.assertEqual(wheel_check.allowed(other['native'], dist, target),
                                 target['id'] == other['id'])

    def test_select_only_requested_target_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'output'
            for name in ('cp310-aarch64', 'cp311-x86_64', 'cp310-x86_64'):
                artifacts = [{'name': 'wheel-source-recipe-' + artifact_suffix(get_target(t)), 'expired': False}
                             for t in ('cp310-aarch64', 'cp311-x86_64', 'cp310-x86_64')]
                run = {'conclusion': 'success', 'head_branch': 'main', 'path': '.github/workflows/wheels.yml', 'event': 'push'}
                with patch.dict(os.environ, {'BUILD_TARGET': name, 'PUBLISH_RUN_ID': '42', 'PUBLISH_SHA256': 'b'*64,
                                             'GITHUB_REPOSITORY': 'owner/wheels', 'GITHUB_OUTPUT': str(output)}), \
                     patch.object(publish, 'api', side_effect=[run, {'artifacts': artifacts}]):
                    publish.resolve()
                self.assertEqual(output.read_text().splitlines()[-1], 'artifact=wheel-source-recipe-' + artifact_suffix(get_target(name)))

    def check_publication(self, damage=None, target_name='cp310-aarch64'):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / 'artifact'
            artifact.mkdir()
            name = 'pyasc_dev-1.1.1.dev1-' + wheel_tag(get_target(target_name)) + '.whl'
            content = b'exact qualified bytes'
            checksum = hashlib.sha256(content).hexdigest()
            (artifact / name).write_bytes(content)
            passport = {'wheel': name, 'wheel_sha256': checksum, 'run_id': '42',
                        'source_repository': 'compiler-team-ru/pyasc', 'target': target_name}
            (artifact / 'build-passport.json').write_text(json.dumps(passport))
            (artifact / 'SHA256SUMS').write_text(''.join(
                hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n'
                for p in sorted(artifact.iterdir())))
            if damage == 'target':
                target_name = 'cp311-x86_64' if target_name == 'cp310-aarch64' else 'cp310-aarch64'
            if damage == 'bytes':
                (artifact / name).write_bytes(b'different bytes')
            if damage == 'extra':
                (artifact / 'debug.log').write_text('not a distribution')
            original = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, {'PUBLISH_RUN_ID': '42', 'PUBLISH_SHA256': checksum, 'BUILD_TARGET': target_name}):
                    publish.check()
                self.assertEqual((root / 'dist' / name).read_bytes(), content)
                self.assertEqual(len(list((root / 'dist').iterdir())), 1)
            finally:
                os.chdir(original)

    def test_publish_exact_bytes_only(self):
        for target in ('cp310-aarch64', 'cp311-x86_64', 'cp310-x86_64'):
            self.check_publication(target_name=target)

    def test_reject_changed_wheel(self):
        with self.assertRaises(AssertionError):
            self.check_publication('bytes')

    def test_reject_wrong_publication_target(self):
        with self.assertRaises(AssertionError):
            self.check_publication('target')

    def test_reject_extra_artifact_file(self):
        with self.assertRaises(AssertionError):
            self.check_publication('extra')

    def test_reject_unqualified_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'PUBLISH_RUN_ID': '1', 'PUBLISH_SHA256': 'b'*64, 'GITHUB_REPOSITORY': 'owner/wheels', 'GITHUB_OUTPUT': directory+'/output'}):
                for run in (
                    {'conclusion': 'failure', 'head_branch': 'main'},
                    {'conclusion': 'success', 'head_branch': 'feature'},
                    {'conclusion': 'success', 'head_branch': 'main', 'path': '.github/workflows/untrusted.yml'},
                    {'conclusion': 'success', 'head_branch': 'main', 'path': '.github/workflows/wheels.yml', 'event': 'pull_request'},
                ):
                    with patch.object(publish, 'api', return_value=run), self.assertRaises(AssertionError):
                        publish.resolve()


if __name__ == '__main__':
    unittest.main()

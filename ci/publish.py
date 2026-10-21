"""Publish the exact wheel selected by a successful build and an explicit hash."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import urllib.error
import urllib.request

from resolve import api


def resolve():
    run_id = os.environ['PUBLISH_RUN_ID']
    assert re.fullmatch(r'[1-9][0-9]*', run_id), 'Invalid build run ID'
    assert re.fullmatch(r'[0-9a-f]{64}', os.environ['PUBLISH_SHA256']), 'A full wheel SHA256 is required'
    repo = os.environ['GITHUB_REPOSITORY']
    run = api(f'repos/{repo}/actions/runs/{run_id}')
    assert run['conclusion'] == 'success' and run['head_branch'] == 'main'
    assert run['path'] == '.github/workflows/wheels.yml'
    assert run['event'] in {'schedule', 'workflow_dispatch', 'push'}
    artifacts = api(f'repos/{repo}/actions/runs/{run_id}/artifacts')['artifacts']
    artifacts = [a for a in artifacts if a['name'].startswith('wheel-') and not a['expired']]
    assert len(artifacts) == 1, 'Expected one retained wheel artifact'
    with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
        f.write('artifact=' + artifacts[0]['name'] + '\n')


def check():
    root = Path('artifact')
    wheels = list(root.glob('*.whl'))
    assert len(wheels) == 1
    wheel = wheels[0]
    assert re.fullmatch(r'pyasc_dev-1\.1\.1\.dev[0-9]+-cp310-cp310-manylinux_2_35_aarch64\.whl', wheel.name)
    assert {p.name for p in root.iterdir()} == {wheel.name, 'build-passport.json', 'SHA256SUMS'}
    expected = {}
    for line in (root / 'SHA256SUMS').read_text().splitlines():
        checksum, name = line.split('  ')
        assert name in {wheel.name, 'build-passport.json'} and name not in expected
        assert re.fullmatch(r'[0-9a-f]{64}', checksum)
        expected[name] = checksum
    assert set(expected) == {wheel.name, 'build-passport.json'}
    for name, checksum in expected.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == checksum
    assert expected[wheel.name] == os.environ['PUBLISH_SHA256'], 'Wheel differs from the qualified bytes'
    passport = json.loads((root / 'build-passport.json').read_text())
    assert passport['wheel_sha256'] == expected[wheel.name]
    assert str(passport['run_id']) == os.environ['PUBLISH_RUN_ID']
    assert passport['wheel'] == wheel.name
    assert passport['source_repository'] == 'compiler-team-ru/pyasc'
    Path('dist').mkdir()
    shutil.copyfile(wheel, Path('dist') / wheel.name)
    print(f"Verified {wheel.name}: {expected[wheel.name]}")


def verify_published():
    passport = json.loads(Path('artifact/build-passport.json').read_text())
    url = f"https://pypi.org/pypi/pyasc-dev/{passport['version']}/json"
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                release = json.load(response)
            match = [f for f in release['urls'] if f['filename'] == passport['wheel']]
            assert len(match) == 1 and match[0]['digests']['sha256'] == os.environ['PUBLISH_SHA256']
            print(f"Published and verified: https://pypi.org/project/pyasc-dev/{passport['version']}/")
            return
        except urllib.error.HTTPError as e:
            if e.code != 404 or attempt == 5:
                raise
            time.sleep(10)


if __name__ == '__main__':
    {'resolve': resolve, 'check': check, 'verify': verify_published}[sys.argv[1]]()

"""Reconcile PyPI bytes and publish a durable manifest only after verification."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request


def fetch(version):
    try:
        with urllib.request.urlopen(f'https://pypi.org/pypi/pyasc-dev/{version}/json?verify={time.time_ns()}', timeout=60) as response:
            return {f['filename']: f for f in json.load(response)['urls']}
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {}
        raise


def reconcile(manifest, files, complete=False):
    for entry in manifest['wheels'].values():
        found = files.get(entry['filename'])
        if found is None:
            if complete:
                raise ValueError('Missing published wheel: ' + entry['filename'])
            continue
        assert found['digests']['sha256'] == entry['sha256'], 'Conflicting PyPI bytes'
        assert not found['yanked'], 'Published wheel is yanked'
        if complete:
            entry['url'] = found['url']


def main():
    mode, filename = sys.argv[1:]
    manifest = json.loads(Path(filename).read_text())
    if mode == 'preflight':
        reconcile(manifest, fetch(manifest['version']))
        return
    assert mode == 'release'
    for attempt in range(12):
        try:
            reconcile(manifest, fetch(manifest['version']), complete=True)
            break
        except ValueError:
            if attempt == 11:
                raise
            time.sleep(10)
    for entry in manifest['wheels'].values():
        digest = hashlib.sha256()
        with urllib.request.urlopen(entry['url'], timeout=120) as response:
            for chunk in iter(lambda: response.read(1024 * 1024), b''):
                digest.update(chunk)
        assert digest.hexdigest() == entry['sha256']
    manifest['status'] = 'complete'
    path = Path('wheel-manifest.json')
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    repo = os.environ['GITHUB_REPOSITORY']
    tag = 'wheel-' + manifest['version']
    existing = subprocess.run(['gh', 'api', f'repos/{repo}/releases/tags/{tag}'], capture_output=True, text=True)
    if existing.returncode == 0:
        release = json.loads(existing.stdout)
        asset = next(a for a in release['assets'] if a['name'] == path.name)
        with urllib.request.urlopen(asset['browser_download_url'], timeout=60) as response:
            assert json.load(response) == manifest, 'Existing manifest differs'
    else:
        # A missing release must be confirmed; auth/network errors are not absence.
        assert '404' in existing.stderr, existing.stderr
        subprocess.run(['gh', 'release', 'create', tag, str(path), '--repo', repo,
                        '--target', os.environ['GITHUB_SHA'], '--title', 'PyAsc wheels ' + manifest['version'],
                        '--notes', 'Complete target qualification. Every published wheel was downloaded from PyPI and verified by SHA256; incompatible targets are listed explicitly.'], check=True)


if __name__ == '__main__':
    main()

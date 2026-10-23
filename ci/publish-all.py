"""Verify and collect every target wheel from one successful build run."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

from target import get_target, wheel_tag


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def main():
    if len(sys.argv) != 4:
        raise SystemExit('usage: publish-all.py ARTIFACTS_DIR DIST_DIR MANIFEST_PATH')
    artifacts = Path(sys.argv[1])
    dist = Path(sys.argv[2])
    manifest_path = Path(sys.argv[3])
    directories = sorted(path for path in artifacts.iterdir() if path.is_dir())
    assert len(directories) == 8, f'Expected eight target artifacts, found {len(directories)}'

    versions = set()
    source_shas = set()
    recipe_shas = set()
    run_ids = set()
    targets = {}
    dist.mkdir(parents=True, exist_ok=True)
    assert not list(dist.iterdir()), 'Distribution directory must be empty'

    for directory in directories:
        assert {path.name for path in directory.iterdir()} == {
            'build-passport.json', 'SHA256SUMS', *(path.name for path in directory.glob('*.whl'))
        }, f'Unexpected files in {directory.name}'
        wheels = list(directory.glob('*.whl'))
        assert len(wheels) == 1, f'Expected one wheel in {directory.name}'
        wheel = wheels[0]
        passport = json.loads((directory / 'build-passport.json').read_text())
        target = get_target(passport['target'])
        expected_name = f"pyasc_dev-{passport['version']}-{wheel_tag(target)}.whl"
        assert wheel.name == expected_name, f'Unexpected wheel name: {wheel.name}'
        assert digest(wheel) == passport['wheel_sha256'], f'Wheel hash mismatch: {wheel.name}'

        sums = {}
        for line in (directory / 'SHA256SUMS').read_text().splitlines():
            checksum, name = line.split('  ')
            assert name in {wheel.name, 'build-passport.json'} and name not in sums
            assert digest(directory / name) == checksum
            sums[name] = checksum
        assert set(sums) == {wheel.name, 'build-passport.json'}
        assert sums[wheel.name] == passport['wheel_sha256']

        assert target['id'] not in targets
        targets[target['id']] = sums[wheel.name]
        versions.add(passport['version'])
        source_shas.add(passport['source_sha'])
        recipe_shas.add(passport['recipe_sha256'])
        run_ids.add(str(passport['run_id']))
        shutil.copyfile(wheel, dist / wheel.name)

    assert len(versions) == 1, 'All target wheels must share one version'
    assert len(source_shas) == 1, 'All target wheels must share one source SHA'
    assert len(recipe_shas) == 1, 'All target wheels must share one recipe SHA'
    assert len(run_ids) == 1, 'All target wheels must come from one run'
    assert len(targets) == 8

    manifest = {
        'version': next(iter(versions)),
        'source_sha': next(iter(source_shas)),
        'recipe_sha256': next(iter(recipe_shas)),
        'run_id': next(iter(run_ids)),
        'targets': targets,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()

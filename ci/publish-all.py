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
    if len(sys.argv) not in (4, 5):
        raise SystemExit('usage: publish-all.py ARTIFACTS_DIR DIST_DIR MANIFEST_PATH [INCOMPATIBILITIES_JSON]')
    artifacts = Path(sys.argv[1])
    dist = Path(sys.argv[2])
    manifest_path = Path(sys.argv[3])
    directories = sorted(path for path in artifacts.iterdir() if path.is_dir())
    incompatible = json.loads(Path(sys.argv[4]).read_text()) if len(sys.argv) == 5 else {}
    assert set(incompatible) <= {'cp39-x86_64', 'cp39-aarch64'}
    assert len(directories) + len(incompatible) == 8, 'Incomplete target qualification'

    versions = set()
    source_shas = set()
    recipe_shas = set()
    run_ids = set()
    targets = {}
    wheels_manifest = {}
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
        wheels_manifest[target['id']] = {
            'filename': wheel.name, 'sha256': sums[wheel.name],
            'llvm': passport['llvm'], 'recipe_commit': passport['recipe_commit'],
            'dependencies': passport['runtime_dependency_wheels'],
        }
        versions.add(passport['version'])
        source_shas.add(passport['source_sha'])
        recipe_shas.add(passport['recipe_sha256'])
        run_ids.add(str(passport['run_id']))
        shutil.copyfile(wheel, dist / wheel.name)

    assert len(versions) == 1, 'All target wheels must share one version'
    assert len(source_shas) == 1, 'All target wheels must share one source SHA'
    assert len(recipe_shas) == 1, 'All target wheels must share one recipe SHA'
    assert len(run_ids) == 1, 'All target wheels must come from one run'
    expected = {f'cp{p}-{a}' for p in ('39', '310', '311', '312') for a in ('x86_64', 'aarch64')}
    assert not set(targets) & set(incompatible)
    assert set(targets) | set(incompatible) == expected
    assert all(e['source_sha'] == next(iter(source_shas)) and e['status'] == 'incompatible'
               and e['job_url'] and e['log_sha256'] for e in incompatible.values())

    manifest = {
        'version': next(iter(versions)),
        'source_sha': next(iter(source_shas)),
        'recipe_sha256': next(iter(recipe_shas)),
        'run_id': next(iter(run_ids)),
        'targets': targets,
        'wheels': wheels_manifest,
        'schema_version': 2,
        'incompatible_targets': incompatible,
        'source_repository': 'compiler-team-ru/pyasc',
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()

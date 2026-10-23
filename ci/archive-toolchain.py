"""Export an installed LLVM toolchain, excluding its source/build/interpreter."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

arch = os.environ['LLVM_ARCH']
revision = 'cd708029e0b2869e80abe31ddb175f7c35361f90'
root = Path('llvm-' + arch)
container = subprocess.check_output(['docker', 'create', 'llvm-export'], text=True).strip()
try:
    subprocess.run(['docker', 'cp', container + ':/opt/llvm', str(root)], check=True)
    subprocess.run(['docker', 'cp', container + ':/opt/licenses/LLVM.txt', str(root / 'LICENSE.TXT')], check=True)
finally:
    subprocess.run(['docker', 'rm', container], check=True)
assert revision in (root / 'include/llvm/Support/VCSRevision.h').read_text()
version = subprocess.check_output(['docker', 'run', '--rm', 'llvm-export', '/opt/llvm/bin/llvm-config', '--version'], text=True).strip()
assert version == '19.1.7'
highest = (0, 0)
count = 0
for path in root.rglob('*'):
    if not path.is_file() or path.is_symlink():
        continue
    with path.open('rb') as stream:
        if stream.read(4) != b'\x7fELF':
            continue
    data = subprocess.check_output(['readelf', '--version-info', str(path)], text=True)
    versions = [tuple(map(int, v.split('.'))) for v in re.findall(r'\bGLIBC_([0-9.]+)', data)]
    if versions:
        highest = max(highest, *versions)
    count += 1
assert count > 0 and highest <= (2, 28), highest
Path('out').mkdir()
archive = Path('out') / (root.name + '.tar.xz')
subprocess.run(['tar', '-I', 'xz -T2 -1', '-cf', str(archive), root.name], check=True)
digest = hashlib.sha256()
with archive.open('rb') as stream:
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(chunk)
passport = {'revision': revision, 'version': version, 'arch': arch, 'sha256': digest.hexdigest(),
            'maximum_glibc': '.'.join(map(str, highest)), 'elf_files': count,
            'builder_recipe': '23f0af9f801fb6cdcd877ccf4b14486bcd3f2f37', 'run_id': os.environ['GITHUB_RUN_ID']}
(archive.parent / (root.name + '.json')).write_text(json.dumps(passport, indent=2) + '\n')
(archive.parent / (root.name + '.sha256')).write_text(digest.hexdigest() + '  ' + archive.name + '\n')

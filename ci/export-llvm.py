"""Export a checked, independently reusable LLVM installation."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

root = Path('/opt/llvm')
lock = json.loads(Path('/opt/toolchain.json').read_text())
assert lock['revision'] == 'cd708029e0b2869e80abe31ddb175f7c35361f90'
assert subprocess.check_output([root / 'bin/llvm-config', '--version'], text=True).strip() == lock['version']
assert lock['revision'] in (root / 'include/llvm/Support/VCSRevision.h').read_text()
assert subprocess.check_output(['getconf', 'GNU_LIBC_VERSION'], text=True).strip() == 'glibc 2.35'
versions = set()
elf_count = 0
for path in root.rglob('*'):
    if not path.is_file() or path.is_symlink():
        continue
    with path.open('rb') as stream:
        if stream.read(4) != b'\x7fELF':
            continue
    elf_count += 1
    info = subprocess.check_output(['readelf', '--version-info', path], text=True)
    versions.update(tuple(map(int, v.split('.'))) for v in re.findall(r'\bGLIBC_([0-9.]+)', info))
assert elf_count and versions and max(versions) <= (2, 35), versions
shutil.copyfile('/opt/licenses/LLVM.txt', root / 'LICENSE.TXT')
output = Path('/out')
assert not list(output.iterdir())
archive = output / 'llvm-cd708029-ubuntu22-x86_64.tar.xz'
subprocess.run(['tar', '--sort=name', '-C', '/opt', '-cJf', str(archive), 'llvm'], check=True,
               env={**os.environ, 'XZ_OPT': '-T2 -3'})
# The builder's system Python is 3.10.
def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()
manifest = {
    'llvm_revision': lock['revision'], 'llvm_version': lock['version'],
    'base_image': lock['base_image'], 'arch': 'x86_64',
    'builder_recipe_commit': 'c42b64cc7905c0259b4c133ae7697a08321d05f7',
    'builder_image_id': os.environ['BUILDER_IMAGE_ID'], 'run_id': os.environ['GITHUB_RUN_ID'],
    'archive': archive.name, 'archive_sha256': digest(archive),
    'maximum_glibc_version': '.'.join(map(str, max(versions))), 'elf_files_checked': elf_count,
    'llvm_cmake_config_sha256': digest(root / 'lib/cmake/llvm/LLVMConfig.cmake'),
    'os_packages': subprocess.check_output(['dpkg-query', '-W'], text=True),
    'scope': 'LLVM installation only; no Python, CANN, source checkout or build tree',
}
(output / 'toolchain-passport.json').write_text(json.dumps(manifest, indent=2) + '\n')
(output / 'SHA256SUMS').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in sorted(output.iterdir())))
print(json.dumps({k: v for k, v in manifest.items() if k != 'os_packages'}))

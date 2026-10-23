"""Export a checked, independently reusable LLVM installation."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


root = Path('/opt/llvm')
revision = 'cd708029e0b2869e80abe31ddb175f7c35361f90'
version = '19.1.7'
arch = os.environ['LLVM_ARCH']
base_image = os.environ['BASE_IMAGE']

assert subprocess.check_output([root / 'bin/llvm-config', '--version'], text=True).strip() == version
assert revision in (root / 'include/llvm/Support/VCSRevision.h').read_text()
assert subprocess.check_output(['getconf', 'GNU_LIBC_VERSION'], text=True).strip() == 'glibc 2.28'

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
    versions.update(tuple(map(int, value.split('.'))) for value in re.findall(r'\bGLIBC_([0-9.]+)', info))
assert elf_count and versions and max(versions) <= (2, 28), versions

shutil.copyfile('/opt/licenses/LLVM.txt', root / 'LICENSE.TXT')
output = Path('/out')
assert not list(output.iterdir())
archive = output / f'llvm-{revision[:8]}-manylinux_2_28-{arch}.tar.xz'
subprocess.run(['tar', '--sort=name', '-C', '/opt', '-cJf', str(archive), 'llvm'], check=True,
               env={**os.environ, 'XZ_OPT': '-T2 -3'})


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


manifest = {
    'llvm_revision': revision,
    'llvm_version': version,
    'base_image': base_image,
    'arch': arch,
    'builder_image_id': os.environ['BUILDER_IMAGE_ID'],
    'run_id': os.environ['GITHUB_RUN_ID'],
    'archive': archive.name,
    'archive_sha256': digest(archive),
    'maximum_glibc_version': '.'.join(map(str, max(versions))),
    'elf_files_checked': elf_count,
    'llvm_cmake_config_sha256': digest(root / 'lib/cmake/llvm/LLVMConfig.cmake'),
    'scope': 'LLVM installation only; no Python, CANN, source checkout or build tree',
}
(output / 'toolchain-passport.json').write_text(json.dumps(manifest, indent=2) + '\n')
(output / 'SHA256SUMS').write_text(''.join(f'{digest(path)}  {path.name}\n' for path in sorted(output.iterdir())))
print(json.dumps(manifest))

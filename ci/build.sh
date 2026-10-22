#!/usr/bin/env bash
set -euo pipefail
export PATH="/opt/build-venv/bin:$PATH"
test "$(git -c safe.directory=/source -C /source rev-parse HEAD)" = "$SOURCE_SHA"
test -z "$(git -c safe.directory=/source -C /source status --porcelain)"
python - <<'PYTHON'
import json
import platform
import subprocess
import sys
import sysconfig
from pathlib import Path
sys.path.insert(0, '/recipe/ci')
from target import get_target
lock = get_target()
assert lock == json.loads(Path('/opt/toolchain.json').read_text())
assert platform.machine() == lock['arch']
assert f'cp{sys.version_info.major}{sys.version_info.minor}' == lock['python_tag']
assert 'asc/_C/libpyasc' + sysconfig.get_config_var('EXT_SUFFIX') == lock['native']
assert subprocess.check_output(['/opt/llvm/bin/llvm-config', '--version'], text=True).strip() == lock['version']
instructions = (Path('/source') / lock['source_instructions']).read_text()
assert lock['revision'] in Path('/opt/llvm/include/llvm/Support/VCSRevision.h').read_text()
assert lock['archive_url'] in instructions, 'Upstream LLVM instructions changed; review toolchain.json before building'
PYTHON
test ! -e /work/source
mkdir /work/source /work/raw /work/build /work/dependencies /work/wheels
git -c safe.directory=/source -C /source archive "$SOURCE_SHA" > /work/source.tar
sha256sum /work/source.tar > /work/source.sha256
tar -xf /work/source.tar -C /work/source
cp /recipe/README.md /work/source/README.md
python3 - <<'PYTHON'
import json
from pathlib import Path
source = json.loads(Path('/recipe/source.json').read_text())
llvm = json.loads(Path('/opt/toolchain.json').read_text())
with Path('/work/source/README.md').open('a') as description:
    description.write('\n## Build provenance\n\n')
    description.write(f"Source: `{source['source_sha']}` in `{source['source_repository']}`.\n\n")
    description.write(f"LLVM revision: `{llvm['revision']}`; build method: `{llvm.get('build_method', 'upstream archive')}`.\n\n")
    description.write(f"Recipe SHA256: `{source['recipe_sha256']}`.\n")
    if source.get('recipe_commit'):
        description.write(f"\nRecipe commit: `{source['recipe_commit']}` in `compiler-team-ru/pyasc-wheels`.\n")
PYTHON
cp /opt/licenses/LLVM.txt /work/source/LICENSE-LLVM.txt
if [ "$BUILD_TARGET" = cp310-aarch64 ]; then
  cp /usr/share/doc/libzstd1/copyright /work/source/LICENSE-ZSTD.txt
fi
export PYASC_SETUP_NAME=pyasc-dev PYASC_SETUP_EXPERIMENTAL=1
export SETUPTOOLS_SCM_PRETEND_VERSION="$WHEEL_VERSION" PYASC_SETUP_VERSION="$WHEEL_VERSION"
export PYASC_SETUP_JOBS=1 PYASC_SETUP_COMPILER=g++
unset PYASC_SETUP_LINKER PYASC_SETUP_CLANG_LLD
export PYASC_SETUP_BUILD_DIR=/work/build
unset PYTHONPATH PYTHONHOME
python -m pip wheel -v --no-build-isolation --no-deps -w /work/raw /work/source
python -m pip download --only-binary=:all: --dest /work/dependencies \
  pybind11==2.10.3 numpy==1.26.4 typing_extensions==4.16.0
auditwheel repair --only-plat --plat "$(python -c 'import sys; sys.path.insert(0,"/recipe/ci"); from target import get_target; print(get_target()["platform"])')" --wheel-dir /work/wheels /work/raw/*.whl
auditwheel show /work/wheels/*.whl > /work/auditwheel.txt
python /recipe/ci/check-wheel.py /work/wheels
for leg in 'clean project A' 'clean project B'; do
  project="/work/$leg"
  mkdir "$project"
  python -m venv "$project/venv"
  "$project/venv/bin/python" -m pip install --no-index --find-links /work/dependencies /work/wheels/*.whl
  "$project/venv/bin/python" -m pip check
  (cd "$project" && "$project/venv/bin/python" -I /recipe/ci/import-smoke.py > result.json)
done
python /recipe/ci/check-wheel.py /work/wheels --finish

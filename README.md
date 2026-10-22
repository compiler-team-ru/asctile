# PyAsc development wheels

`pyasc-dev` provides PyAsc and its experimental AscTile programming model.
It installs the `asc` Python package. Use a dedicated environment; do not
install `pyasc` and `pyasc-dev` together.

## Install

Wheels support these Linux targets:

| Architecture | Python | Minimum glibc |
| --- | --- | --- |
| AArch64 | CPython 3.10 | 2.35 |
| x86_64 | CPython 3.10, 3.11 | 2.35 |

Use the matching interpreter below. Other Python/architecture combinations,
macOS, and Windows are not provided.

```bash
python3.10 -m venv .venv  # Python 3.11 is also supported on x86_64.
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --pre pyasc-dev
python -c 'from asc.experimental import asctile; print(asctile.__file__)'
```

CANN is required to compile and execute kernels and is installed separately.
Kernel execution also needs a C++17 compiler and matching Python headers
(`g++` and the development headers for the selected Python interpreter).
The initial runtime smoke uses CANN 9.0.0 and the Ascend950PR_9599 simulator.
This is a development release, not broad numerical or hardware qualification.

## Build

GitHub Actions checks the default branch of
[compiler-team-ru/pyasc](https://github.com/compiler-team-ru/pyasc) hourly and
supports manual dispatch. The GitCode-to-GitHub mirror is maintained separately.
All targets share an exact source SHA and a development version per run.
Each build uses `PYASC_SETUP_EXPERIMENTAL=1`.
An unchanged source and recipe are skipped while a successful artifact remains
available. Artifacts expire after 90 days.

All builders use Ubuntu 22.04 and checksum-pinned LLVM archives from
[`ci/toolchain.json`](https://github.com/compiler-team-ru/asctile/blob/main/ci/toolchain.json).
The AArch64 archive comes from upstream. The x86_64 archive is stored in
[a GitHub Release](https://github.com/compiler-team-ru/asctile/releases/tag/llvm-cd708029-ubuntu22-x86_64-v1),
with its checksum and build passport. It preserves LLVM revision
`cd708029e0b2869e80abe31ddb175f7c35361f90` and was built with clang and lld on
Ubuntu 22.04. All 135 installed ELF files were checked for GLIBC requirements
no newer than 2.35. The original upstream x86_64 archive requires a newer glibc.

Regular wheel builds download LLVM; they never compile it. The manual
[`llvm.yml`](https://github.com/compiler-team-ru/asctile/blob/main/.github/workflows/llvm.yml)
workflow can reproduce the archive using an immutable builder recipe. It uses
cached layers when available and produces an archive, passport, and checksums
for review before creating a new toolchain release. Release assets are not replaced.

A changed upstream LLVM download URL stops wheel builds for review. PyAsc uses
GCC with its matching linker. CPython 3.10 uses Ubuntu 22.04 system packages.
The Python 3.11 builder uses a checksum-pinned official archive. Docker layers are cached; the LLVM release
remains available independently of that cache. No build trees enter the wheel.

Only the package description and required LLVM/zstd license notices are added
to the exported source. Compiler and runtime code are unchanged. `auditwheel`
checks the ABI and bundles zstd for the AArch64 build that needs it. The resulting wheel is checked for unexpected
files and installed in two fresh environments outside the source directory.

Each target artifact contains exactly one wheel, `build-passport.json`, and
`SHA256SUMS`. Build trees, caches, logs, SDKs, and source checkouts are excluded.
The passport records build inputs and the actual scope of checks. The wheel
metadata also records the source, LLVM, and recipe identifiers, so provenance
survives artifact expiration.

## Publish

Scheduled builds never publish. To publish a checked artifact, manually run
`wheels.yml` with its successful build run ID, `publish_target`, and the wheel's
full SHA256. Publish each qualified target separately.
The publishing job downloads and verifies that artifact; it does not rebuild it.

Trusted Publisher settings:

| Setting | Value |
| --- | --- |
| PyPI project | `pyasc-dev` |
| GitHub owner | `compiler-team-ru` |
| Repository | `asctile` |
| Workflow | `wheels.yml` |
| Environment | `pypi` |

Before publishing, run the CANN smoke on the exact downloaded wheel in a clean
environment outside the repository, with `WHEEL_VERSION` set to its version
and the exact wheel installed:

```bash
source /usr/local/Ascend/cann-9.0.0/set_env.sh
export LD_LIBRARY_PATH="$ASCEND_HOME_PATH/tools/simulator/Ascend950PR_9599/lib:${LD_LIBRARY_PATH:-}"
python -I /path/to/ci/runtime-smoke.py compile
python -I /path/to/ci/runtime-smoke.py model
```

The smoke tests one float32 addition. It does not measure hardware performance.
PyPI versions are immutable: a new build must use a new development version.

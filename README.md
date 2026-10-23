# PyAsc development wheels

`pyasc-dev` provides PyAsc and its experimental AscTile programming model.
It installs the `asc` Python package. Use a dedicated environment; do not
install `pyasc` and `pyasc-dev` together.

## Install

Wheels support these Linux targets:

| Architecture | Python | Minimum glibc |
| --- | --- | --- |
| AArch64 | CPython 3.9, 3.10, 3.11, 3.12 | 2.28 |
| x86_64 | CPython 3.9, 3.10, 3.11, 3.12 | 2.28 |

Use the matching interpreter below. Other Python/architecture combinations,
macOS, and Windows are not provided.

```bash
python3.10 -m venv .venv  # Python 3.9, 3.11, and 3.12 are also supported.
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

All builders use digest-pinned PyPA `manylinux_2_28` images for AArch64 and
x86_64. The images provide CPython 3.9–3.12 and the GNU toolchain. LLVM revision
`cd708029e0b2869e80abe31ddb175f7c35361f90` is built from source inside the same
baseline, so no prebuilt archive with a newer glibc requirement is used.

The manual [`llvm.yml`](https://github.com/compiler-team-ru/asctile/blob/main/.github/workflows/llvm.yml)
workflow builds LLVM on both manylinux architectures and exports an archive,
passport, and checksums for review. Wheel builds use the same source-build
recipe and cached Docker layers. PyAsc is compiled with GCC and its matching
linker. No build trees enter the wheel.

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

The daily run checks whether the exact PyAsc source and build recipe have
already been published. If they have, the workflow stops without rebuilding.
Otherwise, it builds all eight targets, verifies each artifact, and publishes
them together as one PyPI release. The `pypi` environment gates publication.
The publishing job downloads and verifies the eight artifacts from that run;
it does not rebuild them. A successful publication records a marker artifact so
later daily runs can skip the same source and recipe. Use the manual `force`
input to build and publish a new development version.

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

## Image consumers

A successful publication creates a GitHub Release named `wheel-<version>`
with `wheel-manifest.json`. It records the single PyAsc source commit,
wheel recipe, required LLVM revision, and all eight wheel filenames, URLs
and SHA256 hashes. The manifest becomes complete only after every wheel
has been downloaded from PyPI and verified. Container builders consume this
manifest rather than resolving independent "latest" versions per target.

Wheel builders download checksum-pinned LLVM archives from the `llvm-cd708029-manylinux_2_28-v1` release. The native `toolchains.yml` export retains the exact source-built toolchains independently of Python and CANN; wheel jobs never compile LLVM.

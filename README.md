# PyAsc development wheels

`pyasc-dev` provides PyAsc and its experimental AscTile programming model.
It installs the `asc` Python package. Use a dedicated environment; do not
install `pyasc` and `pyasc-dev` together.

## Install

The initial wheel supports **CPython 3.10, Linux AArch64, glibc 2.35 or newer**.
No x86-64, macOS, Windows, or other Python wheels are provided yet.

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --pre pyasc-dev
python -c 'from asc.experimental import asctile; print(asctile.__file__)'
```

CANN is required to compile and execute kernels and is installed separately.
Kernel execution also needs a C++17 compiler and matching Python headers
(`g++` and `python3.10-dev` on Ubuntu 22.04).
The initial runtime smoke uses CANN 9.0.0 and the Ascend950PR_9599 simulator.
This is a development release, not broad numerical or hardware qualification.

## Build

GitHub Actions checks the default branch of
[compiler-team-ru/pyasc](https://github.com/compiler-team-ru/pyasc) hourly and
supports manual dispatch. The GitCode-to-GitHub mirror is maintained separately.
Each build records an exact source SHA and uses `PYASC_SETUP_EXPERIMENTAL=1`.
An unchanged source and recipe are skipped while a successful artifact remains
available. Artifacts expire after 90 days.

The builder uses Ubuntu 22.04 and the exact LLVM archive in
[`ci/toolchain.json`](https://github.com/compiler-team-ru/pyasc-wheels/blob/main/ci/toolchain.json), as specified by the selected PyAsc
source instructions. A changed LLVM download URL stops the build for review.

Only the package description and required LLVM/zstd license notices are added
to the exported source. Compiler and runtime code are unchanged. `auditwheel`
checks the ABI and bundles zstd. The resulting wheel is checked for unexpected
files and installed in two fresh environments outside the source directory.

Each artifact contains exactly one wheel, `build-passport.json`, and
`SHA256SUMS`. Build trees, caches, logs, SDKs, and source checkouts are excluded.
The passport records build inputs and the actual scope of checks. The wheel
metadata also records the source, LLVM, and recipe identifiers, so provenance
survives artifact expiration.

## Publish

Scheduled builds never publish. To publish a checked artifact, manually run
`wheels.yml` with its successful build run ID and the wheel's full SHA256.
The publishing job downloads and verifies that artifact; it does not rebuild it.

Trusted Publisher settings:

| Setting | Value |
| --- | --- |
| PyPI project | `pyasc-dev` |
| GitHub owner | `compiler-team-ru` |
| Repository | `pyasc-wheels` |
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

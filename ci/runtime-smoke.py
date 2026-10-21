"""One fixed add-f32 smoke; not a general numerical qualification suite."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import traceback

# Cache configuration is read during import, so isolate it first.
MODE = sys.argv[1]
if MODE not in {"compile", "model"}:
    raise ValueError(MODE)
os.environ["PYASC_DUMP_PATH"] = str(Path.cwd() / f"dump-{MODE}")
os.environ["PYASC_CACHE_DIR"] = str(Path.cwd() / f"cache-{MODE}")
os.environ["PYASC_DRY_RUN"] = "1" if MODE == "compile" else "0"

import asc
from asc.experimental import asctile
from asc.runtime import config
import numpy as np


@asctile.jit(always_compile=True)
def add_smoke(x_ptr: asctile.GlobalAddress, y_ptr: asctile.GlobalAddress,
              z_ptr: asctile.GlobalAddress):
    x = asctile.global_tensor(x_ptr, [128])
    y = asctile.global_tensor(y_ptr, [128])
    z = asctile.global_tensor(z_ptr, [128])
    a = asctile.copy_in(x, [0], [128])
    b = asctile.copy_in(y, [0], [128])
    asctile.copy_out(a + b, z, [0])


def main():
    root = Path.cwd()
    mode = MODE
    assert sys.prefix != sys.base_prefix, "Expected isolated venv"
    assert importlib.metadata.version("pyasc-dev") == os.environ["WHEEL_VERSION"]
    for module in (asc, asctile):
        assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    try:
        importlib.metadata.distribution("pyasc")
    except importlib.metadata.PackageNotFoundError:
        pass
    else:
        raise AssertionError("Stable pyasc must not coexist in qualification venv")
    config.set_platform("Model", "Ascend950PR_9599", check=True)
    x = np.arange(128, dtype=np.float32)
    y = np.full(128, 2, dtype=np.float32)
    out = np.full(128, np.nan, dtype=np.float32)
    add_smoke[1](x, y, out)
    binary = root / f"dump-{mode}" / "binary.o"
    assert binary.stat().st_size > 0
    if mode == "model":
        np.testing.assert_array_equal(out, x + y)
        np.save(root / "actual.npy", out)
        np.save(root / "expected.npy", x + y)
    else:
        assert np.isnan(out).all(), "Compile-only must leave output untouched"
    return {
        "status": "pass", "mode": mode, "python": sys.version,
        "prefix": sys.prefix, "asc": asc.__file__, "asctile": asctile.__file__,
        "distribution_version": importlib.metadata.version("pyasc-dev"),
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "case": {"operator": "add", "shape": [128], "dtype": "float32", "blocks": 1},
        "scope": "single fixed runtime smoke; broader numerical/hardware qualification not run",
    }


if __name__ == "__main__":
    try:
        result = main()
    except Exception:
        Path(f"result-{sys.argv[1]}.json").write_text(json.dumps({
            "status": "failed", "traceback": traceback.format_exc()
        }, indent=2) + "\n")
        raise
    Path(f"result-{sys.argv[1]}.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))

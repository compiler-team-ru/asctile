"""Check installed Python/native AscTile without claiming a CANN runtime PASS."""
import importlib.metadata
import json
import os
from pathlib import Path
import sys

import asc
from asc.experimental import asctile
from asc._C.libpyasc import asctile as native

assert sys.prefix != sys.base_prefix
assert importlib.metadata.version("pyasc-dev") == os.environ["WHEEL_VERSION"]
for module in (asc, asctile):
    assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
try:
    importlib.metadata.distribution("pyasc")
except importlib.metadata.PackageNotFoundError:
    pass
else:
    raise AssertionError("Unexpected stable PyAsc in clean venv")
assert callable(asctile.jit) and callable(native.ir.load_dialects)
print(json.dumps({"status": "pass", "venv": sys.prefix, "asc": asc.__file__,
                  "asctile": asctile.__file__, "version": importlib.metadata.version("pyasc-dev")}))

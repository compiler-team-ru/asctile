"""Fail closed on unexpected wheel payload; publish only checked bytes and provenance."""
import base64
import csv
from email.parser import BytesParser
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile
from target import get_target, wheel_tag

PACKAGES = {
    "asc", "asc/_C", "asc/codegen", "asc/common", "asc/experimental",
    "asc/language", "asc/language/adv", "asc/language/basic", "asc/language/core", "asc/language/fwk",
    "asc/lib", "asc/lib/host", "asc/lib/profiling", "asc/lib/runtime", "asc/runtime",
    "asc/experimental/asctile", "asc/experimental/asctile/language", "asc/experimental/asctile/runtime",
}
CPP = {"asc/lib/host/bindings/" + n + ".cpp" for n in ("Enums", "MatmulApiTiling", "Module", "Platform")}
CPP |= {"asc/lib/runtime/" + n + ".cpp" for n in ("npu_utils", "print_utils", "rt_wrapper")}
DIST_FILES = {"METADATA", "WHEEL", "RECORD", "top_level.txt", "licenses/LICENSE", "licenses/LICENSE-LLVM.txt", "licenses/LICENSE-ZSTD.txt", "sboms/auditwheel.cdx.json"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def allowed(name, dist, target=None):
    target = target or get_target()
    if name.startswith(dist + "/"):
        return name[len(dist) + 1:] in DIST_FILES
    if re.fullmatch(r"pyasc_dev.libs/libzstd-[0-9a-f]+\.so\.1\.4\.8", name):
        return True
    path = Path(name)
    return name in CPP or name == target['native'] or (path.suffix == ".py" and path.parent.as_posix() in PACKAGES)


def audit(wheel, version):
    target = get_target()
    native_name = target['native']
    dist = f"pyasc_dev-{version}.dist-info"
    with zipfile.ZipFile(wheel) as archive:
        members = archive.namelist()
        assert len(members) == len(set(members))
        names = [n for n in members if not n.endswith('/')]
        parents = {str(p) + '/' for n in names for p in Path(n).parents if str(p) != '.'}
        assert all(n in parents for n in members if n.endswith('/')), "Unexpected empty directory"
        assert len(names) == len(set(names)), "Duplicate ZIP members"
        assert all(allowed(n, dist) for n in names), "Unexpected file in wheel: " + repr([n for n in names if not allowed(n, dist)])
        assert {native_name, "asc/experimental/asctile/__init__.py", *(dist + "/" + n for n in DIST_FILES)} <= set(names), "Missing package or license metadata"
        metadata = BytesParser().parsebytes(archive.read(f"{dist}/METADATA"))
        assert metadata["Name"] == "pyasc-dev" and metadata["Version"] == version
        assert "Tag: " + wheel_tag(target) in archive.read(f"{dist}/WHEEL").decode()
        records = list(csv.reader(io.StringIO(archive.read(f"{dist}/RECORD").decode())))
        assert len(records) == len(names) and {r[0] for r in records} == set(names)
        for name, checksum, size in records:
            if name == f"{dist}/RECORD":
                assert checksum == size == ""
            else:
                data = archive.read(name)
                actual = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
                assert checksum == "sha256=" + actual and int(size) == len(data), name
        native = archive.read(native_name)
    return {"wheel_sha256": digest(wheel), "files": len(names), "native_sha256": hashlib.sha256(native).hexdigest()}, native


def main():
    target = get_target()
    wheels = list(Path(sys.argv[1]).glob("*.whl"))
    assert len(wheels) == 1
    wheel = wheels[0]
    version = os.environ["WHEEL_VERSION"]
    result, native = audit(wheel, version)
    native_path = Path("/work/native.so")
    native_path.write_bytes(native)
    dynamic = subprocess.check_output(["readelf", "-d", str(native_path)], text=True)
    paths = re.findall(r"\((?:RPATH|RUNPATH)\).*?\[([^\]]+)\]", dynamic)
    assert paths == ["$ORIGIN/../../pyasc_dev.libs"], paths
    needed = re.findall(r"Shared library: \[([^\]]+)\]", dynamic)
    loader = {'aarch64': 'ld-linux-aarch64.so.1', 'x86_64': 'ld-linux-x86-64.so.2'}[target['arch']]
    assert {n for n in needed if not re.fullmatch(r"libzstd-[0-9a-f]+\.so\.1\.4\.8", n)} <= {"libm.so.6", "libz.so.1", "libstdc++.so.6", "libgcc_s.so.1", "libc.so.6", loader}, needed
    result["native_dependencies"] = needed
    if "--finish" not in sys.argv:
        Path("/work/audit.json").write_text(json.dumps(result))
        print(json.dumps(result))
        return
    assert json.loads(Path("/work/audit.json").read_text()) == result, "Wheel changed during qualification"
    checks = [json.loads((Path("/work") / name / "result.json").read_text()) for name in ("clean project A", "clean project B")]
    assert all(r["status"] == "pass" and r["version"] == version for r in checks)
    source = json.loads(Path("/recipe/source.json").read_text())
    assert source["source_sha"] == os.environ["SOURCE_SHA"]
    passport = {
        **source, "version": version, "wheel": wheel.name, **result,
        "source_archive_sha256": digest(Path("/work/source.tar")),
        "builder_image_id": os.environ["BUILDER_IMAGE_ID"],
        "target": target['id'], "base_image": target['base_image'],
        "llvm": target,
        "packaging_overlay": "README.md and third-party license notices only; compiler source unchanged",
        "package_description_sha256": digest(Path("/work/source/README.md")),
        "auditwheel": Path("/work/auditwheel.txt").read_text(),
        "compiler": subprocess.check_output(["g++", "--version"], text=True),
        "build_dependencies": subprocess.check_output([sys.executable, "-m", "pip", "freeze", "--all"], text=True),
        "os_packages": subprocess.check_output(["dpkg-query", "-W"], text=True),
        "runtime_dependency_wheels": {p.name: digest(p) for p in Path("/work/dependencies").glob("*.whl")},
        "clean_install_import_checks": checks,
        "cann_compile": "not-run", "numerical": "not-run", "hardware": "not-run",
        "qualification_scope": "packaging, native dependencies, two clean installations and imports only",
        "run_id": os.environ.get("GITHUB_RUN_ID", "local"), "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
    }
    output = Path("/out")
    assert not list(output.iterdir()), "Output directory must be empty"
    shutil.copyfile(wheel, output / wheel.name)
    (output / "build-passport.json").write_text(json.dumps(passport, indent=2) + "\n")
    (output / "SHA256SUMS").write_text("".join(digest(p) + "  " + p.name + "\n" for p in sorted(output.iterdir())))
    print(json.dumps({"status": "pass", **result}))


if __name__ == "__main__":
    main()

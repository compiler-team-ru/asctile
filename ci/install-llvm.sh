#!/usr/bin/env bash
set -euo pipefail
value() { python3 -c "import json; print(json.load(open('/opt/toolchain.json'))['$1'])"; }
curl --fail --location --connect-timeout 20 --max-time 900 "$(value archive_url)" -o /tmp/llvm.tar.xz
echo "$(value archive_sha256)  /tmp/llvm.tar.xz" | sha256sum -c -
mkdir /opt/llvm
tar -xJf /tmp/llvm.tar.xz -C /opt/llvm --strip-components=1
rm /tmp/llvm.tar.xz

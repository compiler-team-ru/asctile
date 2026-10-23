#!/usr/bin/env bash
# Durable architecture-specific toolchains; no compiler build in wheel jobs.
set -euo pipefail
arch=$(uname -m)
case "$arch" in
  x86_64) sha=fed5edd62bfd553678149b5b73d65bc17f5300bfe34a538bbe8790a8a64c8a7f ;;
  aarch64) sha=adabb4a47ab3c839e08b4cc99a9f22d0775cd800648b7e4f8992c24143373edb ;;
  *) echo "Unsupported LLVM architecture: $arch" >&2; exit 1 ;;
esac
url="https://github.com/compiler-team-ru/asctile/releases/download/llvm-cd708029-manylinux_2_28-v1/llvm-${arch}.tar.xz"
curl -fL --retry 3 "$url" -o /tmp/llvm.tar.xz
printf '%s  /tmp/llvm.tar.xz\n' "$sha" | sha256sum -c -
mkdir -p /opt/llvm /opt/licenses
tar -xJf /tmp/llvm.tar.xz -C /opt/llvm --strip-components=1
rm /tmp/llvm.tar.xz
cp /opt/llvm/LICENSE.TXT /opt/licenses/LLVM.txt
grep -F 'cd708029e0b2869e80abe31ddb175f7c35361f90' /opt/llvm/include/llvm/Support/VCSRevision.h
test "$(/opt/llvm/bin/llvm-config --version)" = 19.1.7

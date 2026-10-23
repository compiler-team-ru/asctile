#!/usr/bin/env bash
set -euo pipefail

revision=cd708029e0b2869e80abe31ddb175f7c35361f90
case "$(uname -m)" in
  x86_64) llvm_target=X86 ;;
  aarch64) llvm_target=AArch64 ;;
  *) echo "Unsupported architecture: $(uname -m)" >&2; exit 2 ;;
esac

git init /tmp/llvm-source
git -C /tmp/llvm-source remote add origin https://github.com/llvm/llvm-project.git
git -C /tmp/llvm-source fetch --depth 1 origin "$revision"
git -C /tmp/llvm-source checkout --detach FETCH_HEAD
test "$(git -C /tmp/llvm-source rev-parse HEAD)" = "$revision"

cmake -S /tmp/llvm-source/llvm -B /tmp/llvm-build -G "Unix Makefiles" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/opt/llvm \
  -DCMAKE_C_COMPILER=gcc \
  -DCMAKE_CXX_COMPILER=g++ \
  -DLLVM_ENABLE_PROJECTS=mlir \
  -DLLVM_TARGETS_TO_BUILD="$llvm_target" \
  -DLLVM_ENABLE_ASSERTIONS=ON \
  -DLLVM_ENABLE_RTTI=OFF \
  -DLLVM_ENABLE_EH=OFF \
  -DLLVM_ENABLE_ZLIB=ON \
  -DLLVM_ENABLE_ZSTD=OFF \
  -DLLVM_ENABLE_LIBXML2=OFF \
  -DLLVM_ENABLE_TERMINFO=OFF \
  -DLLVM_INCLUDE_TESTS=OFF \
  -DMLIR_INCLUDE_TESTS=OFF \
  -DLLVM_INCLUDE_BENCHMARKS=OFF \
  -DLLVM_INCLUDE_EXAMPLES=OFF \
  -DLLVM_PARALLEL_COMPILE_JOBS=2 \
  -DLLVM_PARALLEL_LINK_JOBS=1
cmake --build /tmp/llvm-build --target install --parallel 2
rm -rf /tmp/llvm-source /tmp/llvm-build

mkdir -p /opt/licenses
curl --fail --location --connect-timeout 20 --max-time 120 \
  https://raw.githubusercontent.com/llvm/llvm-project/cd708029e0b2869e80abe31ddb175f7c35361f90/llvm/LICENSE.TXT \
  -o /opt/licenses/LLVM.txt
echo '8d85c1057d742e597985c7d4e6320b015a9139385cff4cbae06ffc0ebe89afee  /opt/licenses/LLVM.txt' | sha256sum -c -

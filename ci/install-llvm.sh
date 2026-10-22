#!/usr/bin/env bash
set -euo pipefail
value() { python3 -c "import json; print(json.load(open('/opt/toolchain.json'))['$1'])"; }
if [ "$BUILD_TARGET" = cp311-x86_64 ]; then
  # Rebuild the upstream archive's exact revision against Ubuntu 22.04.
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends clang lld cmake ninja-build
  rm -rf /var/lib/apt/lists/*
  git init /tmp/llvm-source
  git -C /tmp/llvm-source remote add origin "$(value source_repository)"
  git -C /tmp/llvm-source fetch --depth 1 origin "$(value revision)"
  git -C /tmp/llvm-source checkout --detach FETCH_HEAD
  test "$(git -C /tmp/llvm-source rev-parse HEAD)" = "$(value revision)"
  cmake -S /tmp/llvm-source/llvm -B /tmp/llvm-build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/llvm \
    -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DLLVM_USE_LINKER=lld \
    -DLLVM_ENABLE_PROJECTS=mlir -DLLVM_TARGETS_TO_BUILD=X86 \
    -DLLVM_ENABLE_ASSERTIONS=ON -DLLVM_ENABLE_RTTI=OFF -DLLVM_ENABLE_EH=OFF \
    -DLLVM_ENABLE_ZLIB=ON -DLLVM_ENABLE_ZSTD=OFF -DLLVM_ENABLE_LIBXML2=OFF \
    -DLLVM_ENABLE_TERMINFO=OFF -DLLVM_INCLUDE_TESTS=OFF -DMLIR_INCLUDE_TESTS=OFF \
    -DLLVM_INCLUDE_BENCHMARKS=OFF -DLLVM_INCLUDE_EXAMPLES=OFF \
    -DLLVM_PARALLEL_COMPILE_JOBS=2 -DLLVM_PARALLEL_LINK_JOBS=1
  cmake --build /tmp/llvm-build --target install --parallel 2
  rm -rf /tmp/llvm-source /tmp/llvm-build
else
  curl --fail --location --connect-timeout 20 --max-time 900 "$(value archive_url)" -o /tmp/llvm.tar.xz
  echo "$(value archive_sha256)  /tmp/llvm.tar.xz" | sha256sum -c -
  mkdir /opt/llvm
  tar -xJf /tmp/llvm.tar.xz -C /opt/llvm --strip-components=1
  rm /tmp/llvm.tar.xz
fi

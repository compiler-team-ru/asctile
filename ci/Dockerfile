# Ubuntu 22.04 (AArch64) or 24.04 (x86_64). No CANN, installed PyAsc, torch, agents, or source checkout.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG BUILD_TARGET
ENV BUILD_TARGET=${BUILD_TARGET}
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates curl git xz-utils python3 python3-dev python3-venv \
      build-essential zlib1g-dev libzstd-dev libtinfo-dev \
    && rm -rf /var/lib/apt/lists/*
COPY ci/toolchain.json ci/target.py /opt/recipe/
RUN python3 -c 'import sys,json; sys.path.insert(0,"/opt/recipe"); from target import get_target; json.dump(get_target(),open("/opt/toolchain.json","w"))'
# CPython 3.11 is built from the official, checksum-pinned source on Ubuntu 24.04.
# Keep this interpreter private to the builder; it is not included in the wheel.
RUN if [ "$BUILD_TARGET" = cp311-x86_64 ]; then \
      apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        libssl-dev libffi-dev libbz2-dev libreadline-dev libsqlite3-dev liblzma-dev libncursesw5-dev libgdbm-dev uuid-dev \
      && rm -rf /var/lib/apt/lists/* \
      && curl --fail --location --connect-timeout 20 --max-time 300 \
        "$(python3 -c 'import json; print(json.load(open("/opt/toolchain.json"))["python_source_url"])')" -o /tmp/python.tar.xz \
      && echo "$(python3 -c 'import json; print(json.load(open("/opt/toolchain.json"))["python_source_sha256"])')  /tmp/python.tar.xz" | sha256sum -c - \
      && mkdir /tmp/python && tar -xJf /tmp/python.tar.xz -C /tmp/python --strip-components=1 \
      && cd /tmp/python && ./configure --prefix=/opt/python --enable-shared --with-ensurepip=install LDFLAGS=-Wl,-rpath=/opt/python/lib \
      && make -j2 && make install \
      && /opt/python/bin/python3.11 -c 'import ssl, ctypes, bz2, lzma, sqlite3, venv' \
      && cd / && rm -rf /tmp/python /tmp/python.tar.xz; \
    fi
RUN curl --fail --location --connect-timeout 20 --max-time 900 \
      "$(python3 -c 'import json; print(json.load(open("/opt/toolchain.json"))["archive_url"])')" \
      -o /tmp/llvm.tar.xz \
    && echo "$(python3 -c 'import json; print(json.load(open("/opt/toolchain.json"))["archive_sha256"])')  /tmp/llvm.tar.xz" | sha256sum -c - \
    && mkdir /opt/llvm \
    && tar -xJf /tmp/llvm.tar.xz -C /opt/llvm --strip-components=1 \
    && rm /tmp/llvm.tar.xz
RUN mkdir /opt/licenses \
    && curl --fail --location --connect-timeout 20 --max-time 120 \
      https://raw.githubusercontent.com/llvm/llvm-project/cd708029e0b2869e80abe31ddb175f7c35361f90/llvm/LICENSE.TXT \
      -o /opt/licenses/LLVM.txt \
    && echo '8d85c1057d742e597985c7d4e6320b015a9139385cff4cbae06ffc0ebe89afee  /opt/licenses/LLVM.txt' | sha256sum -c -
COPY ci/requirements-build.lock /opt/requirements-build.lock
RUN "$(python3 -c 'import json; print(json.load(open("/opt/toolchain.json"))["python_bin"])')" -m venv /opt/build-venv \
    && /opt/build-venv/bin/python -m pip install --no-cache-dir -r /opt/requirements-build.lock
ENV LLVM_INSTALL_PREFIX=/opt/llvm
WORKDIR /work

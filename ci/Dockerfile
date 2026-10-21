# Ubuntu 22.04 arm64. No CANN, installed PyAsc, torch, agents, or source checkout.
FROM ubuntu@sha256:88881eb36da489f9ff8746ece8048ca16cc94f80e8cd3ae7e8335d8822631591
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates curl git xz-utils python3 python3-dev python3-venv \
      build-essential zlib1g-dev libzstd-dev libtinfo-dev \
    && rm -rf /var/lib/apt/lists/*
COPY ci/toolchain.json /opt/toolchain.json
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
RUN python3 -m venv /opt/build-venv \
    && /opt/build-venv/bin/python -m pip install --no-cache-dir -r /opt/requirements-build.lock
ENV LLVM_INSTALL_PREFIX=/opt/llvm
WORKDIR /work

# PyPA manylinux_2_28. No CANN, installed PyAsc, torch, agents, or source checkout.
ARG BASE_IMAGE=quay.io/pypa/manylinux_2_28_x86_64@sha256:076b19ef6e698f28649fa817c49d14443201e01da85240e8e52f93e8daa49bff
FROM ${BASE_IMAGE}
ARG BUILD_TARGET
ENV BUILD_TARGET=${BUILD_TARGET}

COPY ci/toolchain.json ci/target.py /opt/recipe/
RUN python3 -c 'import sys,json; sys.path.insert(0,"/opt/recipe"); from target import get_target; json.dump(get_target(),open("/opt/toolchain.json","w"))'

COPY ci/build-llvm.sh /opt/recipe/build-llvm.sh
RUN bash /opt/recipe/build-llvm.sh

COPY ci/requirements-build.lock /opt/requirements-build.lock
RUN "$(python3 -c 'import json; print(json.load(open("/opt/toolchain.json"))["python_bin"])')" -m venv /opt/build-venv \
    && /opt/build-venv/bin/python -m pip install --no-cache-dir -r /opt/requirements-build.lock

ENV LLVM_INSTALL_PREFIX=/opt/llvm
WORKDIR /work

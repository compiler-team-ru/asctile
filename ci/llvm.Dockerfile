# PyPA manylinux_2_28 LLVM-only builder.
ARG BASE_IMAGE=quay.io/pypa/manylinux_2_28_x86_64@sha256:076b19ef6e698f28649fa817c49d14443201e01da85240e8e52f93e8daa49bff
FROM ${BASE_IMAGE}

COPY ci/build-llvm.sh /opt/recipe/build-llvm.sh
RUN bash /opt/recipe/build-llvm.sh

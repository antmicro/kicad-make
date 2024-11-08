ARG BASE_IMAGE=kicad/kicad
ARG BASE_TAG=8.0

FROM ${BASE_IMAGE}:${BASE_TAG}

COPY dist/*.whl /dist/

RUN apt update && \
    apt install -y pip && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --break-system-packages --no-deps /dist/*.whl

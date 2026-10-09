# Standalone JAX environment: never install training dependencies into the
# production Needle inference add-on.
ARG PYTHON_BASE=python:3.11-slim-bookworm
FROM ${PYTHON_BASE}
ARG BUILD_ARCH=amd64
ARG NEEDLE_VERSION=3.1.3

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    JAX_PLATFORMS=cpu \
    PIP_NO_CACHE_DIR=1 \
    NEEDLE_TELEMETRY=0 \
    DO_NOT_TRACK=1 \
    NEEDLE3_LIB_PATH=/opt/needle-engine/libneedle.so \
    NEEDLE_LIB_PATH=/opt/needle-engine/libneedle.so

# Bundle the generation-3 *native* inference engine at build time.
# Runtime evaluation is HF_HUB_OFFLINE=1, so it must not fetch libraries.
# Same engine download command as the regular Needle inference add-on.
RUN python3 -m pip install --no-cache-dir "cactus-needle[train]==${NEEDLE_VERSION}" \
    && python3 -m pip check \
    && case "${BUILD_ARCH}" in \
        amd64) platform_tag="manylinux2014_x86_64" ;; \
        aarch64) platform_tag="manylinux2014_aarch64" ;; \
        *) echo "Unsupported build architecture: ${BUILD_ARCH}" >&2; exit 1 ;; \
    esac \
    && mkdir -p /opt/needle-engine \
    && needle fetch --out /opt/needle-engine --platform-tag "${platform_tag}" \
    && test -s /opt/needle-engine/libneedle.so
COPY app/ /app/
WORKDIR /app

# Does not expose a port, access HA APIs, require privileged mode, or auto-run.
ENTRYPOINT ["python3", "-u", "/app/runner.py"]

ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION

LABEL io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version="${BUILD_VERSION}" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.version="${BUILD_VERSION}" \
    org.opencontainers.image.licenses="MIT"

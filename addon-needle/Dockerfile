# Needle ships a manylinux (glibc) native library, so this add-on must use a
# Debian/glibc image. Do not use Home Assistant's Alpine-based base image here.
FROM python:3.11-slim-bookworm

ARG BUILD_ARCH=amd64
ARG NEEDLE_VERSION=3.0.1

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV \
    HOME=/data \
    HF_HOME=/data/huggingface \
    JAX_PLATFORMS=cpu \
    NEEDLE_LIB_PATH=/opt/needle-engine/libneedle.so \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install --no-install-recommends --yes \
        ca-certificates \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --no-cache-dir "cactus-needle==${NEEDLE_VERSION}" \
    # Needle 3.0.1 uses origin-root URLs (for example /style.css and /model).
    # Home Assistant ingress mounts the app below a tokenized path, so make all
    # bundled UI resources and API calls relative to that ingress path.
    && playground="/usr/local/lib/python3.11/site-packages/needle/playground" \
    && grep -Fq 'href="/style.css"' "${playground}/index.html" \
    && grep -Fq 'src="/app.js"' "${playground}/index.html" \
    && grep -Fq 'fetch("/' "${playground}/app.js" \
    && grep -Fq 'dl.href = "/download/' "${playground}/app.js" \
    && sed -i \
        -e 's|href="/style.css"|href="./style.css"|g' \
        -e 's|src="/app.js"|src="./app.js"|g' \
        "${playground}/index.html" \
    && sed -i \
        -e 's|fetch("/|fetch("./|g' \
        -e 's|dl.href = "/download/|dl.href = "./download/|g' \
        "${playground}/app.js" \
    && case "${BUILD_ARCH}" in \
        amd64) platform_tag="manylinux2014_x86_64" ;; \
        aarch64) platform_tag="manylinux2014_aarch64" ;; \
        *) echo "Unsupported architecture: ${BUILD_ARCH}" >&2; exit 1 ;; \
    esac \
    && mkdir -p /opt/needle-engine \
    && needle fetch \
        --out /opt/needle-engine \
        --platform-tag "${platform_tag}" \
    && test -s /opt/needle-engine/libneedle.so

COPY rootfs /

RUN chmod 0755 /app/entrypoint.sh /app/healthcheck.sh

WORKDIR /data

EXPOSE 7860

ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=2m \
    --retries=3 \
    CMD ["/app/healthcheck.sh"]

ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION

LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version="${BUILD_VERSION}" \
    maintainer="Marcel Rösler <me@marcel.codes>" \
    org.opencontainers.image.title="${BUILD_NAME}" \
    org.opencontainers.image.description="${BUILD_DESCRIPTION}" \
    org.opencontainers.image.vendor="Marcel Rösler" \
    org.opencontainers.image.authors="Marcel Rösler <me@marcel.codes>" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.documentation="https://github.com/${BUILD_REPOSITORY}/blob/main/addon-needle/DOCS.md" \
    org.opencontainers.image.created="${BUILD_DATE}" \
    org.opencontainers.image.revision="${BUILD_REF}" \
    org.opencontainers.image.version="${BUILD_VERSION}"

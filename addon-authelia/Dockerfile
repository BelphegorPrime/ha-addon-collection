ARG BUILD_FROM=ghcr.io/hassio-addons/base:17.2.4
FROM ${BUILD_FROM}

ARG BUILD_ARCH=amd64

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG VERSION="v4.38.19"

ENV \
    PUID=0 \
    PGID=0 \
    X_AUTHELIA_CONFIG="/config/configuration.yml" \
    AUTHELIA_LOG_LEVEL="trace"

# Copy root filesystem
COPY rootfs /

# ARCH Mapping und Binary holen
RUN \
    if [[ "${BUILD_ARCH}" == "aarch64" ]]; then export ARCH="arm64"; \
    elif [[ "${BUILD_ARCH}" == "amd64" ]]; then export ARCH="amd64"; \
    elif [[ "${BUILD_ARCH}" == "armv7" ]]; then export ARCH="arm"; \
    else echo "Unsupported arch: ${BUILD_ARCH}" && exit 1; fi \
    && mkdir -p /opt/authelia \
    && curl -L -s \
        "https://github.com/authelia/authelia/releases/download/${VERSION}/authelia-${VERSION}-linux-${ARCH}-musl.tar.gz" \
        | tar zxvf - -C /opt/authelia \
    && cp /opt/authelia/authelia-linux-${ARCH}-musl /usr/local/bin/authelia \
    && rm -rf /opt/authelia

RUN chmod +x /usr/local/bin/authelia /app/entrypoint.sh /app/healthcheck.sh

# Ports
EXPOSE 9091

ENTRYPOINT ["/app/entrypoint.sh"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=1m CMD /app/healthcheck.sh

# Build arguments
ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_DESCRIPTION
ARG BUILD_NAME
ARG BUILD_REF
ARG BUILD_REPOSITORY
ARG BUILD_VERSION

# Labels
LABEL \
    io.hass.name="${BUILD_NAME}" \
    io.hass.description="${BUILD_DESCRIPTION}" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    maintainer="Marcel Rösler <me@marcel.codes>" \
    org.opencontainers.image.title="${BUILD_NAME}" \
    org.opencontainers.image.description="${BUILD_DESCRIPTION}" \
    org.opencontainers.image.vendor="Home Assistant Community Add-ons" \
    org.opencontainers.image.authors="Marcel Rösler <me@marcel.codes>" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.url="https://addons.community" \
    org.opencontainers.image.source="https://github.com/${BUILD_REPOSITORY}" \
    org.opencontainers.image.documentation="https://github.com/${BUILD_REPOSITORY}/blob/main/README.md" \
    org.opencontainers.image.created=${BUILD_DATE} \
    org.opencontainers.image.revision=${BUILD_REF} \
    org.opencontainers.image.version=${BUILD_VERSION}

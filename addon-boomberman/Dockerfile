ARG BUILD_FROM=ghcr.io/belphegorprime/boomberman
FROM ${BUILD_FROM}:v${BUILD_VERSION}

ARG BUILD_ARCH=amd64
ARG BASHIO_VERSION="v0.17.0"
ARG TEMPIO_VERSION="2024.11.2"

ENV \
    PUID=0 \
    PGID=0 \
    LOG_LEVEL="trace"

RUN apk update && apk upgrade && apk add --no-cache bash curl jq

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Copy root filesystem
COPY rootfs /

RUN curl -J -L -o /tmp/bashio.tar.gz "https://github.com/hassio-addons/bashio/archive/${BASHIO_VERSION}.tar.gz"
RUN mkdir /tmp/bashio
RUN tar zxvf /tmp/bashio.tar.gz --strip 1 -C /tmp/bashio
RUN mv /tmp/bashio/lib /usr/lib/bashio

RUN curl -sSLf -o /bin/tempio "https://github.com/home-assistant/tempio/releases/download/${TEMPIO_VERSION}/tempio_${BUILD_ARCH}" \
    && chmod +x /bin/tempio

# ARCH Mapping und Binary holen
RUN \
    if [[ "${BUILD_ARCH}" == "aarch64" ]]; then export ARCH="arm64"; \
    elif [[ "${BUILD_ARCH}" == "amd64" ]]; then export ARCH="amd64"; \
    else echo "Unsupported arch: ${BUILD_ARCH}" && exit 1; fi

RUN chmod +x /start/entrypoint.sh /start/healthcheck.sh

# Ports
EXPOSE 9092

ENTRYPOINT ["/start/entrypoint.sh"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=1m CMD /start/healthcheck.sh

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

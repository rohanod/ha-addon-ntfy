# Pinned official upstream image. scripts/appctl.py rewrites this line on upgrade.
FROM binwiederhier/ntfy:v2.38.3@sha256:874299b207a9815e7a0cf551b3a094241db7604fa2d274bbd86f569154b6ea51

ARG BUILD_VERSION
ARG BUILD_ARCH
LABEL io.hass.version="${BUILD_VERSION}" io.hass.type="app" io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache jq
COPY run.sh /run.sh
RUN chmod a+x /run.sh

ENTRYPOINT ["/run.sh"]

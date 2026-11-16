# Pinned official upstream image. scripts/appctl.py rewrites this line on upgrade.
FROM binwiederhier/ntfy:v2.38.1@sha256:038da2be5e668fee6d36a62884eea48975e1b71c29a56964e5298c1b9165a573

ARG BUILD_VERSION
ARG BUILD_ARCH
LABEL io.hass.version="${BUILD_VERSION}" io.hass.type="app" io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache jq
COPY run.sh /run.sh
RUN chmod a+x /run.sh

ENTRYPOINT ["/run.sh"]

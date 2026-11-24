# Pinned official upstream image. scripts/appctl.py rewrites this line on upgrade.
FROM binwiederhier/ntfy:v2.38.2@sha256:ca35419d29a834824db2440fa9320897fbe40b026c5fc2360c76ed3501b5e716

ARG BUILD_VERSION
ARG BUILD_ARCH
LABEL io.hass.version="${BUILD_VERSION}" io.hass.type="app" io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache jq
COPY run.sh /run.sh
RUN chmod a+x /run.sh

ENTRYPOINT ["/run.sh"]

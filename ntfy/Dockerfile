# Pinned official upstream image. scripts/appctl.py rewrites this line on upgrade.
FROM binwiederhier/ntfy:v2.35.0@sha256:6f0c9abab7b99a978d816611cc90dabb4849b81f60c53114e91cd07931085dc0

ARG BUILD_VERSION
ARG BUILD_ARCH
LABEL io.hass.version="${BUILD_VERSION}" io.hass.type="app" io.hass.arch="${BUILD_ARCH}"

RUN apk add --no-cache jq
COPY run.sh /run.sh
RUN chmod a+x /run.sh

ENTRYPOINT ["/run.sh"]

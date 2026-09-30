FROM alpine:3.24

RUN apk add --no-cache mpd

COPY entrypoint.sh /entrypoint.sh

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD printf 'close\n' | nc -w 3 127.0.0.1 6600 | grep -q '^OK MPD'

ENTRYPOINT ["/entrypoint.sh"]

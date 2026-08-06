# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN python -m pip wheel --wheel-dir /wheels .


FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ARG APP_UID=10001
ARG APP_GID=10001

ENV HOME=/var/lib/movie-inbox \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid "${APP_GID}" movie-inbox \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --home-dir /var/lib/movie-inbox \
        --shell /usr/sbin/nologin movie-inbox

COPY --from=builder /wheels/ /wheels/

RUN python -m pip install --no-index --find-links=/wheels movie-inbox \
    && rm -rf /wheels \
    && install -d -o movie-inbox -g movie-inbox \
        /var/lib/movie-inbox /var/lib/movie-inbox/catalogs /var/lib/movie-inbox/image-cache \
    && install -d /media/library \
    && for slot in 1 2 3 4 5 6 7 8; do \
        install -d "/media/library/disco${slot}"; \
    done

USER movie-inbox:movie-inbox
WORKDIR /var/lib/movie-inbox

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "from urllib.request import urlopen; response = urlopen('http://127.0.0.1:8765/healthz', timeout=3); raise SystemExit(0 if response.status == 200 else 1)"]

ENTRYPOINT ["movie-inbox"]
CMD ["--help"]

ARG BUILD_FROM=ghcr.io/hassio-addons/base:20.1.1

# ---------- Stage 1: build the frontend ----------
# Pinned to the *build* platform, not the target. This stage emits static
# JS/CSS, which is platform-independent, so there is nothing to gain from
# emulating the target — and `node:24-alpine` publishes no linux/arm/v7
# image at all, so building for armv7 failed here before reaching any of
# our own code. Running natively also avoids QEMU for the whole npm and
# Vite step, which dominates the cross-architecture build.
FROM --platform=$BUILDPLATFORM node:24-alpine AS fe-builder

WORKDIR /fe
COPY apps/frontend/package.json apps/frontend/package-lock.json ./
RUN npm ci
COPY apps/frontend/ ./
# Types (src/api/generated.ts) are generated against a running backend ahead
# of the Docker build via CI; if building locally without CI, run
# `npm run gen:api` before `docker build`.
RUN npm run build

# ---------- Stage 2: runtime ----------
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1

# `re2` and `abseil-cpp` are runtime libraries, kept in the image. cel-python
# depends on google-re2, which publishes no musllinux wheel, so on Alpine it
# is always compiled from source — hence the toolchain below, added and
# removed in one layer so it never reaches the final image.
RUN apk add --no-cache python3 py3-pip re2 abseil-cpp

COPY apps/backend/pyproject.toml apps/backend/uv.lock /app/
WORKDIR /app
# `--no-dev` alone does not exclude the `dev` extra — that is a separate
# concept from dependency groups — so `--all-extras` was shipping pytest,
# mypy and ruff into the production image.
RUN apk add --no-cache --virtual .build-deps g++ re2-dev abseil-cpp-dev python3-dev py3-pybind11-dev && \
    pip install --no-cache-dir --break-system-packages uv && \
    uv sync --frozen --no-dev && \
    apk del .build-deps

COPY apps/backend/src /app/src
COPY apps/backend/alembic /app/alembic
COPY apps/backend/alembic.ini /app/alembic.ini
COPY --from=fe-builder /fe/dist /app/static

COPY home-curator/run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]

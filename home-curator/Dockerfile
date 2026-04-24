ARG BUILD_FROM=ghcr.io/hassio-addons/base:15.0.9

# ---------- Stage 1: build the frontend ----------
FROM node:22-alpine AS fe-builder

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

RUN apk add --no-cache python3 py3-pip

COPY apps/backend/pyproject.toml apps/backend/uv.lock /app/
WORKDIR /app
RUN pip install --no-cache-dir --break-system-packages uv && \
    uv sync --all-extras --frozen --no-dev

COPY apps/backend/src /app/src
COPY apps/backend/alembic /app/alembic
COPY apps/backend/alembic.ini /app/alembic.ini
COPY --from=fe-builder /fe/dist /app/static

COPY home-curator/run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]

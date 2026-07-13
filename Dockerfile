FROM node:22-slim AS web-build

WORKDIR /app

COPY web/package.json web/package-lock.json ./web/
RUN cd web && npm ci

COPY web ./web
RUN cd web && npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY pyproject.toml uv.lock* ./
COPY src ./src
COPY --from=web-build /app/src/qingluo_console/static ./src/qingluo_console/static
RUN pip install --no-cache-dir --retries 5 --timeout 120 uv && \
    uv pip install --system .

EXPOSE 8010
CMD ["uvicorn", "qingluo_console.main:app", "--host", "0.0.0.0", "--port", "8010"]

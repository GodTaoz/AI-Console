FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock* ./
COPY src ./src
RUN pip install --no-cache-dir uv && \
    uv pip install --system .

EXPOSE 8010
CMD ["uvicorn", "qingluo_console.main:app", "--host", "0.0.0.0", "--port", "8010"]

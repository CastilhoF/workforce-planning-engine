FROM python:3.14.9-slim-bookworm AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

FROM base AS dev

COPY requirements.txt requirements-dev.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY app ./app
COPY pyproject.toml ./pyproject.toml

EXPOSE 8020

CMD ["sh", "-c", "python3.14 -m uvicorn app.main:app --host ${APP_HOST:-0.0.0.0} --port ${APP_PORT:-8020} --reload"]

FROM base AS runtime

COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY pyproject.toml ./pyproject.toml

EXPOSE 8020

CMD ["sh", "-c", "python3.14 -m uvicorn app.main:app --host ${APP_HOST:-0.0.0.0} --port ${APP_PORT:-8020}"]

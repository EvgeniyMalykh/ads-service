# syntax=docker/dockerfile:1
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Зависимости ставятся строго по uv.lock (--frozen/--locked: lock-файл не пересобирается).
# Dev-группа (pytest, ruff) нужна, чтобы тесты запускались внутри контейнера.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project

COPY . .

RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py loaddata authors && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -"]

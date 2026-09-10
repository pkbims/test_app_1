# Single image, used for api / worker / dashboard — same code, different entrypoint.
# Tradeoff: one image is simpler to build and reason about on camera, and guarantees
# the three processes run identical code. It also means the worker image carries the
# web deps and vice versa. At this size that is a few MB, not a real cost; revisit
# with a multi-stage split only if the image grows.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Dev + runtime deps in one layer. The dev deps (pytest, ruff, mypy) are here so the
# same image runs the test suite in CI and locally via `docker compose run`.
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

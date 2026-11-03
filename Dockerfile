# The envoituresimone web app, for Railway (or any container host).
# Build: docker build -t envoituresimone .
# Run:   docker run -p 8000:8000 -e ORS_API_KEY=... -v $PWD/data:/app/data envoituresimone
# Mount a persistent volume on /app/data: it holds the hourly price snapshot and its history.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8000 DATA_DIR=/app/data \
    TZ=Europe/Paris
WORKDIR /app

# Dependencies first (cached layer). --no-default-groups: no pytest, no genau-kit (private repo).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-default-groups --no-install-project

COPY src/ src/
RUN mkdir -p /app/data
EXPOSE 8000
CMD ["/app/.venv/bin/python", "src/app.py"]

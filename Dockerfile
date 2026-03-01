FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends ffmpeg \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY proxima ./proxima

RUN uv sync --no-dev

CMD ["uv", "run", "python", "-m", "proxima.main"]

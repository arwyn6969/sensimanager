# SWOS420 — main application image
#
# Usage:
#   docker build -t swos420 .
#   docker run --rm swos420                           # run tests (default)
#   docker run --rm swos420 python -m swos420         # run the app
#   docker run --rm swos420 python scripts/run_full_season.py --season 25/26 --min-squad-size 1

FROM python:3.12-slim AS base

LABEL maintainer="arwyn6969 <arwyn6969@github>"
LABEL description="SWOS420 — AI football league simulator"

WORKDIR /app

# Install dependencies first for layer caching
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir -e ".[dev,ai]"

# Copy the rest of the project
COPY config/ config/
COPY scripts/ scripts/
COPY tests/ tests/
COPY data/ data/
COPY contracts/ contracts/
COPY streaming/ streaming/

# Default: run test suite to verify the build
CMD ["python", "-m", "pytest", "-q"]

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 10001 worker

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN pip install --no-cache-dir .

USER worker
CMD ["python", "-m", "software_factory.services.runner.main"]

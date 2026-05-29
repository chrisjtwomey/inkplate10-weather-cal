FROM python:3.13-slim-bookworm

ARG SERVER_VERSION=v1.3.1
ARG SERVER_COMMIT_SHA=

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    CHROME_BIN=/usr/bin/chromium \
    SERVER_VERSION=${SERVER_VERSION} \
    SERVER_COMMIT_SHA=${SERVER_COMMIT_SHA}

RUN apt-get update && apt-get install --no-install-recommends -y \
        chromium \
        chromium-driver \
        fonts-dejavu-core \
        tini \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/sh app
WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip setuptools wheel && pip install -r requirements.txt

COPY . /app
# Seed the runtime config from the example so the image is runnable with
# only `docker run -e WEATHER_APIKEY=... -e GOOGLE_APIKEY=... ...`. Mount a
# real /app/config.yaml at runtime to override every key at once instead.
RUN cp config.example.yaml config.yaml \
    && python -c "import json, os; json.dump({'version': os.environ.get('SERVER_VERSION', 'dev'), 'commitSha': os.environ.get('SERVER_COMMIT_SHA', '')}, open('/app/version.json', 'w'))" \
    && chmod +x /app/entrypoint.sh \
    && chown -R app:app /app

USER app
EXPOSE 8080

ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]

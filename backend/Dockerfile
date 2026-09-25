# VayuDRISHTI backend image.
#
# Build from the backend/ directory so the context stays small:
#   docker build -t vayudrishti-api backend/
#   docker run -p 8000:8000 vayudrishti-api
#
# The trained artifacts in app/ml_models are copied in, so the container serves
# predictions without a training step. Rebuild only if you retrain.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# curl is used by the container healthcheck below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first so application edits do not invalidate the pip layer.
COPY requirements.txt .
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt

COPY app ./app
COPY run.py .

# Run unprivileged.
RUN useradd --create-home --shell /usr/sbin/nologin vayu \
    && chown -R vayu:vayu /srv
USER vayu

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

# --proxy-headers and --forwarded-allow-ips let the platform's TLS terminator
# pass through correctly, and a single worker keeps the in-process attribution
# cache coherent.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

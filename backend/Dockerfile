# Backend image for the WV Education News Desk (self-hosted).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# NOTE (temporary, removed in migration Phase 5 / hard cut):
# the code shipped today still imports `emergentintegrations`, which is served
# from Emergent's package index. The extra-index-url lets the CURRENT build run
# in Docker. Once the LLM/email providers are swapped to direct SDKs, delete
# `emergentintegrations` from requirements.txt and drop the extra index below.
RUN pip install -r requirements.txt \
    --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/

COPY . .

EXPOSE 8001

# Simple container healthcheck against a lightweight public endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=5 \
    CMD curl -fsS http://localhost:8001/api/schedule/next || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]

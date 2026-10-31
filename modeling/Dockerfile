# API-et (Python). Bygg: docker compose build api
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/app/src
WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt \
 && pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY src ./src
COPY config ./config
COPY scripts ./scripts

# data/ (etiketter) og models/ (trente modeller) monteres som volumer i docker-compose.yml
RUN mkdir -p data/labels models
EXPOSE 8000
CMD ["uvicorn", "klatreforhold.api:app", "--host", "0.0.0.0", "--port", "8000"]

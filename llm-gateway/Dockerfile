FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY llm-gateway/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared /app/shared
COPY llm-gateway /app/llm-gateway

ENV PYTHONPATH=/app

EXPOSE 7000

CMD ["uvicorn", "llm-gateway.main:app", "--host", "0.0.0.0", "--port", "7000"]

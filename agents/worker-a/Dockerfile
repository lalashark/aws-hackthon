FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY agents/worker-a/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared /app/shared
COPY agents/common /app/agents/common
COPY agents/worker-a /app/agents/worker-a

ENV PYTHONPATH=/app

EXPOSE 5000

CMD ["uvicorn", "agents.worker-a.main:app", "--host", "0.0.0.0", "--port", "5000"]

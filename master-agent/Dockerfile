FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY master-agent/requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared /app/shared
COPY master-agent /app/master-agent

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "master-agent.main:app", "--host", "0.0.0.0", "--port", "8000"]

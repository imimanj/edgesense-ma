FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY shared /app/shared
COPY services /app/services
CMD ["python", "-m", "uvicorn", "services.audio_service.app.main:app", "--host", "0.0.0.0", "--port", "8003"]

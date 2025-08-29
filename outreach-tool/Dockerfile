FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

# Install Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy API code
COPY api /app/api

EXPOSE 8000

ENV WEB_CONCURRENCY=1

CMD ["gunicorn", "api.index:app", "-b", "0.0.0.0:8000", "--workers", "1", "--threads", "8", "--timeout", "120"]



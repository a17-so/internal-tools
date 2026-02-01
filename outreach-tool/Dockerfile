FROM python:3.10-slim-bookworm

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY requirements.txt ./requirements.txt

# Create config config directory and copy env.yaml explicitly
RUN mkdir -p /app/config
COPY api/envs/env.yaml /app/config/env.yaml

# Install Python dependencies
RUN pip install --no-cache-dir -r ./requirements.txt

# Copy the entire application
COPY . .

# Set environment variables
ENV FLASK_APP=api/main.py
ENV PYTHONPATH=/app:/app/api

# Expose port
EXPOSE 8080

# Run the application with gunicorn
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 60 --chdir /app/api main:app

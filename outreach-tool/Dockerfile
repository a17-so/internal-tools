FROM python:3.10-slim

WORKDIR /app

# Install system dependencies needed for Playwright and Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    libu2f-udev \
    libvulkan1 \
    && rm -rf /var/lib/apt/lists/*

# Copy top-level requirements first (if exists)
COPY requirements.txt ./requirements.txt

# Copy api requirements and install Python dependencies
COPY api/requirements.txt ./api/requirements.txt
RUN pip install --no-cache-dir -r ./api/requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium || true

# Copy the entire application
COPY . .

# Set environment variables
ENV FLASK_APP=api/index.py
ENV PYTHONPATH=/app:/app/api

# Expose port
EXPOSE 8080

# Run the application with gunicorn - use main:app directly since index.py just imports from main
# Using shell form (not exec form) to ensure $PORT is expanded correctly
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 60 --chdir /app/api main:app


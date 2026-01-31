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

# Copy requirements files
COPY requirements.txt ./requirements.txt
COPY api/requirements.txt ./api/requirements.txt

# Install Python dependencies (including Playwright)
RUN pip install --no-cache-dir -r ./api/requirements.txt

# Install Playwright browsers AFTER pip install
# Use PLAYWRIGHT_BROWSERS_PATH to ensure consistent location
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN python3 -m playwright install chromium --with-deps

# Verify Playwright installation
RUN python3 -c "from playwright.sync_api import sync_playwright; print('Playwright installed successfully')"

# Copy the entire application
COPY . .

# Set environment variables
ENV FLASK_APP=api/index.py
ENV PYTHONPATH=/app:/app/api

# Expose port
EXPOSE 8080

# Run the application with gunicorn
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 60 --chdir /app/api main:app

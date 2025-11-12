FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

# Copy requirements
COPY api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY . /app/

# Set environment variables
ENV FLASK_APP=api.index
ENV PORT=8080
ENV USE_ARC=false

# Expose port
EXPOSE 8080

# Run the application
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 600 api.index:app


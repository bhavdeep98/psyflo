FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY ../../shared /app/feelwell/shared

# Copy service code
COPY . /app/feelwell/services/analytics_service

# Set Python path
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8080

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "feelwell.services.analytics_service.handler:app"]
